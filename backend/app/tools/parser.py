
from __future__ import annotations

import json
import re
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

import pandas as pd
import pdfplumber
from docx import Document


SUPPORTED_FORMATS = {
    ".pdf", ".xlsx", ".csv", ".docx", ".txt", ".eml", ".json"
}

COLUMN_ALIASES = {
    "name": {"vendor", "vendor_name", "supplier", "supplier_name", "name"},
    "price": {"price", "unit_price", "price_inr", "cost", "amount", "price_rs"},
    "ram_gb": {"ram", "ram_gb", "memory", "memory_gb"},
    "ssd_gb": {"ssd", "ssd_gb", "storage", "storage_gb"},
    "delivery_days": {"delivery", "delivery_days", "lead_time", "lead_time_days"},
    "warranty_years": {"warranty", "warranty_years", "warranty_yrs"},
}


def _number(value: Any) -> float | int | None:
    """Convert an explicitly supplied value to a number."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return value if pd.notna(value) else None

    text = str(value).strip().lower().replace(",", "")
    if not text:
        return None

    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None

    number = float(match.group())
    return int(number) if number.is_integer() else number


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized_keys = {
        re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_"): value
        for key, value in row.items()
    }

    result: dict[str, Any] = {}

    for field, aliases in COLUMN_ALIASES.items():
        value = None

        for key, candidate in normalized_keys.items():
            if key in aliases and candidate is not None and str(candidate).strip():
                value = candidate
                break

        if field == "name":
            result[field] = str(value).strip() if value is not None else None
        else:
            result[field] = _number(value)

    # Convert explicitly labelled TB storage values to GB.
    for field in ("ram_gb", "ssd_gb"):
        raw_value = next(
            (
                str(value).strip().lower()
                for key, value in normalized_keys.items()
                if key in COLUMN_ALIASES[field]
                and value is not None
                and str(value).strip()
            ),
            "",
        )

        if result[field] is not None and re.search(r"\btb\b", raw_value):
            result[field] *= 1024

    # Support an explicit warranty_months column.
    warranty_months = _number(normalized_keys.get("warranty_months"))
    if result["warranty_years"] is None and warranty_months is not None:
        result["warranty_years"] = warranty_months / 12
    elif result["warranty_years"] is not None:
        warranty_raw = str(normalized_keys.get("warranty", "")).lower()
        if "month" in warranty_raw:
            result["warranty_years"] /= 12

    result["missing_fields"] = [
        field for field in COLUMN_ALIASES if result.get(field) is None
    ]
    result["complete"] = not result["missing_fields"]
    return result


    
def _extract_text_fields(text: str) -> dict[str, Any]:
    """Extract explicitly labelled quotation fields, including vendor name."""

    patterns = {
        "name": r"^\s*(?:vendor|supplier)(?:\s+name)?\s*[:\-]\s*(.+?)\s*$",
        "price": r"^\s*(?:(?:unit\s+)?price|cost|amount)\s*(?:inr|rs\.?|₹)?\s*[:\-]\s*₹?\s*([\d,]+(?:\.\d+)?)",
        "ram_gb": r"^\s*(?:ram|memory)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:gb)?",
        "ssd_gb": r"^\s*(?:ssd|storage)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(gb|tb)?",
        "delivery_days": r"^\s*(?:delivery|lead\s*time)\s*[:\-]?\s*(\d+)\s*days?",
        "warranty_years": r"^\s*warranty\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(years?|yrs?|months?)?",
    }

    result: dict[str, Any] = {}

    for field, pattern in patterns.items():
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )

        if match is None:
            result[field] = None
            continue

        result[field] = (
            match.group(1).strip()
            if field == "name"
            else _number(match.group(1))
        )

        if field == "ssd_gb" and (match.group(2) or "").lower() == "tb":
            result[field] *= 1024

        if (
            field == "warranty_years"
            and (match.group(2) or "").lower().startswith("month")
        ):
            result[field] /= 12

    result["missing_fields"] = [
        field for field in COLUMN_ALIASES if result.get(field) is None
    ]
    result["complete"] = not result["missing_fields"]

    return result



def _read_text_file(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")

    if suffix == ".docx":
        document = Document(path)
        parts = [paragraph.text for paragraph in document.paragraphs]

        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))

        return "\n".join(parts)

    if suffix == ".pdf":
        pages = []

        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")

                for table in page.extract_tables():
                    for row in table:
                        pages.append(" | ".join(cell or "" for cell in row))

        return "\n".join(pages)

    if suffix == ".eml":
        with path.open("rb") as file:
            message = BytesParser(policy=policy.default).parse(file)

        parts = []

        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    content = part.get_content()
                    if isinstance(content, str):
                        parts.append(content)
        elif message.get_content_type() == "text/plain":
            content = message.get_content()
            if isinstance(content, str):
                parts.append(content)

        return "\n".join(parts)

    raise ValueError(f"Text extraction is not supported for {suffix}")


def parse_quotation(file_path: str | Path) -> dict[str, Any]:
    """
    Parse a quotation into normalized vendor records.

    Supported: PDF, XLSX, CSV, DOCX, TXT, EML and JSON.
    Missing fields are reported rather than invented.
    """
    path = Path(file_path)

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Quotation file not found: {path}")

    suffix = path.suffix.lower()

    if suffix not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported format: {suffix}. "
            f"Supported formats: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )

    vendors: list[dict[str, Any]] = []
    warnings: list[str] = []
    raw_text = ""

    if suffix in {".csv", ".xlsx"}:
        frame = (
            pd.read_csv(path)
            if suffix == ".csv"
            else pd.read_excel(path)
        )

        records = frame.astype(object).where(pd.notna(frame), None).to_dict(
            orient="records"
        )
        vendors = [_normalize_row(row) for row in records]

    elif suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))

        if isinstance(data, dict):
            rows = data.get("vendors", [data])
        elif isinstance(data, list):
            rows = data
        else:
            raise ValueError(
                "JSON must contain an object or a list of vendor objects."
            )

        if not isinstance(rows, list) or not all(
            isinstance(row, dict) for row in rows
        ):
            raise ValueError("JSON vendors must be a list of objects.")

        vendors = [_normalize_row(row) for row in rows]

    else:
        raw_text = _read_text_file(path)

        if not raw_text.strip():
            warnings.append(
                "No extractable text found. This may be a scanned PDF "
                "or an email without a plain-text body."
            )
        else:
            record = _extract_text_fields(raw_text)
            vendors = [record]

            if not record["complete"]:
                warnings.append(
                    "Some fields could not be extracted confidently; "
                    "manual review is required."
                )

    if not vendors:
        warnings.append("No vendor records were extracted.")

    return {
        "source_file": path.name,
        "format": suffix.lstrip("."),
        "vendors": vendors,
        "raw_text": raw_text,
        "warnings": warnings,
    }
