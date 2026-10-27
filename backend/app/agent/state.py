
from typing import Any, TypedDict


class ProcurementState(TypedDict, total=False):
    requirements: dict[str, Any]

    # Universal mode: category-independent rules (see dynamic_constraints.py).
    # When present, vendors are judged against these instead of the
    # fixed laptop fields in `requirements`.
    constraints: list[dict[str, Any]]
    vendor_records: list[dict[str, Any]]
    evaluation_results: list[dict[str, Any]]
    ranked_vendors: list[dict[str, Any]]
    errors: list[str]

    # AI quotation extraction and explanation
    ai_explanations: list[dict[str, Any]]
    ai_warnings: list[str]

    approval_status: str
    selected_vendor: dict[str, Any] | None
    approval_decision: dict[str, Any] | None
