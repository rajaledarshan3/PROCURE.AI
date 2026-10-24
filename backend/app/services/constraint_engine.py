
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


def rank_vendors(results):
    eligible = [v for v in results if v["eligible"]]
    eligible.sort(key=lambda v: v["price"])

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
                "Excluded because mandatory requirements failed"
            )

    return results
