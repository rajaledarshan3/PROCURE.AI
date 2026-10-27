from app.services.dynamic_constraints import evaluate_constraints


def evaluate_vendor(requirements, vendor):
    failures = []

    if vendor.ram_gb < requirements.min_ram_gb:
        failures.append(
            f"RAM {vendor.ram_gb}GB is below the "
            f"{requirements.min_ram_gb}GB minimum"
        )

    if vendor.ssd_gb < requirements.min_ssd_gb:
        failures.append("SSD capacity is below minimum")

    if vendor.price > requirements.max_price:
        failures.append("Price exceeds the budget")

    if vendor.delivery_days > requirements.max_delivery_days:
        failures.append("Delivery exceeds the deadline")

    if vendor.warranty_years < requirements.min_warranty_years:
        failures.append("Warranty is below minimum")

    return {
        "vendor": vendor.name,
        "price": vendor.price,
        "eligible": len(failures) == 0,
        "status": "Eligible" if not failures else "Not eligible",
        "reasons": failures,
    }


_STATUS_LABELS = {
    "eligible": "Eligible",
    "not_eligible": "Not eligible",
    "needs_review": "Needs review",
    "invalid_constraints": "Invalid constraints",
}


def evaluate_vendor_dynamic(vendor: dict, constraints: list[dict]) -> dict:
    """Judge one vendor (any fields) against category-independent rules.

    Returns the same shape as evaluate_vendor(), plus the detailed
    mandatory_failures / preferred_misses / missing_fields lists.
    """
    raw = evaluate_constraints(vendor, constraints)

    reasons = [
        f"{item['field']} must be {item['operator']} "
        f"{item['expected']} (got {item['actual']})"
        for item in raw["mandatory_failures"]
    ]
    reasons += [
        f"Missing data for '{field}'; manual review required"
        for field in raw["missing_fields"]
    ]
    reasons += raw["errors"]

    return {
        "vendor": vendor.get("name") or "Unnamed vendor",
        "price": vendor.get("price"),
        "eligible": raw["eligible"],
        "status": _STATUS_LABELS.get(raw["status"], raw["status"]),
        "reasons": reasons,
        "mandatory_failures": raw["mandatory_failures"],
        "preferred_misses": raw["preferred_misses"],
        "missing_fields": raw["missing_fields"],
    }


def rank_vendors(results):
    """Rank eligible vendors by lowest price (fewer preferred misses win ties)."""
    eligible = [v for v in results if v["eligible"]]
    eligible.sort(
        key=lambda v: (
            v["price"] if v.get("price") is not None else float("inf"),
            len(v.get("preferred_misses", [])),
        )
    )

    for rank, vendor in enumerate(eligible, start=1):
        vendor["rank"] = rank
        vendor["recommendation_reason"] = (
            "Lowest-priced eligible vendor"
            if rank == 1
            else "Eligible; ranked by price"
        )

    for vendor in results:
        if not vendor["eligible"]:
            vendor["rank"] = None
            vendor["recommendation_reason"] = (
                "Excluded until the missing information is reviewed"
                if vendor.get("status") == "Needs review"
                else "Excluded because mandatory requirements failed"
            )

    return results
