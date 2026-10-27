
from typing import Any

from google.genai.errors import APIError
from pydantic import BaseModel, Field

from app.agent.state import ProcurementState
from app.services.constraint_engine import (
    evaluate_vendor,
    evaluate_vendor_dynamic,
    rank_vendors,
)
from app.services.gemini_service import (
    explain_recommendation,
    extract_vendor_quotation,
)
from app.tools.parser import parse_quotation


class RequirementsModel(BaseModel):
    min_ram_gb: float = Field(ge=0)
    min_ssd_gb: float = Field(ge=0)
    max_price: float = Field(gt=0)
    max_delivery_days: int = Field(gt=0)
    min_warranty_years: float = Field(ge=0)


class VendorModel(BaseModel):
    name: str
    price: float = Field(gt=0)
    ram_gb: float = Field(ge=0)
    ssd_gb: float = Field(ge=0)
    delivery_days: int = Field(ge=0)
    warranty_years: float = Field(ge=0)


def constraint_fields(constraints: list[dict[str, Any]]) -> list[str]:
    """Fields to extract from a quotation: name, price and every rule field."""
    fields = ["name", "price"]
    for rule in constraints:
        field = rule.get("field")
        if isinstance(field, str) and field and field not in fields:
            fields.append(field)
    return fields


def parse_quotations_node(state: ProcurementState) -> dict[str, Any]:
    records = list(state.get("vendor_records", []))
    errors = list(state.get("errors", []))
    parsed_records = []

    # Universal mode: extract exactly the fields the rules need.
    constraints = state.get("constraints")
    fields = constraint_fields(constraints) if constraints else None

    for record in records:
        if not isinstance(record, str):
            parsed_records.append(record)
            continue

        try:
            parsed = parse_quotation(record)
            vendors = parsed.get("vendors", [])
            raw_text = parsed.get("raw_text", "").strip()
            errors.extend(parsed.get("warnings", []))

            # Use Gemini when local extraction is empty or incomplete.
            if fields:
                needs_ai = not vendors or any(
                    vendor.get(field) is None
                    for vendor in vendors
                    for field in fields
                )
            else:
                needs_ai = not vendors or any(
                    vendor.get("missing_fields") for vendor in vendors
                )

            if needs_ai and raw_text:
                try:
                    ai_result = (
                        extract_vendor_quotation(raw_text, fields=fields)
                        if fields
                        else extract_vendor_quotation(raw_text)
                    )
                    ai_vendors = ai_result.get("vendors", [])
                    errors.extend(ai_result.get("warnings", []))

                    if ai_vendors:
                        vendors = ai_vendors
                    else:
                        errors.append(
                            f"{record}: Gemini extracted no vendor records; "
                            "manual review is required."
                        )

                except (APIError, RuntimeError, ValueError, TypeError) as exc:
                    errors.append(
                        f"{record}: Gemini extraction failed; "
                        f"using local parser results. {exc}"
                    )

            if not vendors:
                errors.append(
                    f"{record}: No vendor records could be extracted."
                )

            parsed_records.extend(vendors)

        except (ValueError, OSError) as exc:
            errors.append(f"Could not parse {record}: {exc}")

    return {
        "vendor_records": parsed_records,
        "errors": errors,
    }


def evaluate_vendors_dynamic(
    state: ProcurementState,
    constraints: list[dict[str, Any]],
) -> dict[str, Any]:
    """Universal evaluation: any product category, rules come from data."""
    results = []
    errors = list(state.get("errors", []))

    for index, record in enumerate(
        state.get("vendor_records", []), start=1
    ):
        if not isinstance(record, dict):
            errors.append(f"Vendor record {index} is not a valid record.")
            continue

        result = evaluate_vendor_dynamic(record, constraints)

        if result["missing_fields"]:
            errors.append(
                f"{result['vendor']} has missing data for: "
                + ", ".join(result["missing_fields"])
            )

        results.append(result)

    ranked = rank_vendors(results)

    return {
        "evaluation_results": results,
        "ranked_vendors": ranked,
        "errors": errors,
    }


def evaluate_vendors_node(state: ProcurementState) -> dict[str, Any]:
    constraints = state.get("constraints")
    if constraints:
        return evaluate_vendors_dynamic(state, constraints)

    requirements = RequirementsModel.model_validate(state["requirements"])
    results = []
    errors = list(state.get("errors", []))

    for index, record in enumerate(
        state.get("vendor_records", []), start=1
    ):
        if record.get("missing_fields"):
            errors.append(
                f"{record.get('name') or f'Vendor {index}'} has missing fields: "
                + ", ".join(record["missing_fields"])
            )
            continue

        try:
            vendor = VendorModel.model_validate(record)
            results.append(evaluate_vendor(requirements, vendor))
        except (ValueError, TypeError) as exc:
            errors.append(f"Vendor record {index} is invalid: {exc}")

    ranked = rank_vendors(results)

    return {
        "evaluation_results": results,
        "ranked_vendors": ranked,
        "errors": errors,
    }


def prepare_approval_node(state: ProcurementState) -> dict[str, Any]:
    ranked = state.get("ranked_vendors", [])

    winner = next(
        (
            vendor
            for vendor in ranked
            if vendor.get("eligible") and vendor.get("rank") == 1
        ),
        None,
    )

    updates: dict[str, Any] = {
        "selected_vendor": winner,
        "approval_status": (
            "pending" if winner else "no_eligible_vendor"
        ),
    }

    source_warnings = list(state.get("errors", []))

    if not winner:
        updates["ai_explanations"] = {
            "summary": (
                "No vendor satisfies all mandatory procurement requirements."
            ),
            "selected_vendor_reason": "",
        }
        updates["ai_warnings"] = source_warnings
        return updates

    # Find the original vendor record to ground missing-field warnings.
    selected_name = winner.get("vendor") or winner.get("name")
    vendor_records = state.get("vendor_records", [])

    selected_record = next(
        (
            record
            for record in vendor_records
            if (record.get("name") or record.get("vendor")) == selected_name
        ),
        {},
    )

    missing_fields = selected_record.get("missing_fields", [])
    if missing_fields:
        source_warnings.append(
            f"{selected_name} has missing fields: "
            + ", ".join(missing_fields)
        )

    # Universal mode: tell the reviewer which nice-to-have rules were missed.
    for miss in winner.get("preferred_misses", []):
        got = "no data" if miss["actual"] is None else miss["actual"]
        source_warnings.append(
            f"{selected_name} does not meet the preferred requirement "
            f"{miss['field']} {miss['operator']} {miss['expected']} "
            f"(got {got})."
        )

    # Gemini explains the result; Python remains authoritative for ranking.
    try:
        explanation = explain_recommendation(
            requirements=state["requirements"],
            ranked_vendors=ranked,
            selected_vendor=winner,
            warnings=source_warnings,
        )

        updates["ai_explanations"] = {
            "summary": explanation.get("summary", ""),
            "selected_vendor_reason": explanation.get(
                "selected_vendor_reason", ""
            ),
        }

        ai_warnings = explanation.get("warnings", [])
        if not isinstance(ai_warnings, list):
            ai_warnings = []

        updates["ai_warnings"] = list(
            dict.fromkeys(source_warnings + ai_warnings)
        )

    except (APIError, RuntimeError, ValueError, TypeError) as exc:
        # AI failure must not stop procurement or human approval.
        updates["ai_explanations"] = {
            "summary": (
                "Vendor ranking completed using the procurement rules."
            ),
            "selected_vendor_reason": winner.get(
                "recommendation_reason",
                "Highest-ranked eligible vendor.",
            ),
        }
        updates["ai_warnings"] = source_warnings + [
            f"AI explanation unavailable: {exc}"
        ]

    return updates


def record_approval_node(state: ProcurementState) -> dict[str, Any]:
    decision = state.get("approval_decision") or {}
    approved = decision.get("approved")

    if approved is True:
        status = "approved"
    elif approved is False:
        status = "rejected"
    else:
        status = "invalid_decision"

    return {"approval_status": status}
