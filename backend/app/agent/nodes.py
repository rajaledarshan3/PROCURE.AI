
from typing import Any

from pydantic import BaseModel, Field

from app.agent.state import ProcurementState
from app.services.constraint_engine import evaluate_vendor, rank_vendors
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


def parse_quotations_node(state: ProcurementState) -> dict[str, Any]:
    records = list(state.get("vendor_records", []))
    errors = list(state.get("errors", []))
    parsed_records = []

    for record in records:
        if isinstance(record, str):
            try:
                parsed = parse_quotation(record)
                parsed_records.extend(parsed["vendors"])
                errors.extend(parsed.get("warnings", []))
            except (ValueError, OSError) as exc:
                errors.append(f"Could not parse {record}: {exc}")
        else:
            parsed_records.append(record)

    return {"vendor_records": parsed_records, "errors": errors}


def evaluate_vendors_node(state: ProcurementState) -> dict[str, Any]:
    requirements = RequirementsModel.model_validate(state["requirements"])
    results = []
    errors = list(state.get("errors", []))

    for index, record in enumerate(state.get("vendor_records", []), start=1):
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
        (vendor for vendor in ranked if vendor.get("eligible")),
        None,
    )

    return {
        "selected_vendor": winner,
        "approval_status": "pending" if winner else "no_eligible_vendor",
    }


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
