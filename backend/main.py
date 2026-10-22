
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI(
    title="PROCURE.AI",
    description="Agentic AI Procurement Prototype",
    version="0.1.0"
)


class Requirements(BaseModel):
    quantity: int = 50
    min_ram_gb: int = 16
    min_ssd_gb: int = 512
    max_price: float = 60000
    max_delivery_days: int = 15
    min_warranty_years: int = 3


class Vendor(BaseModel):
    name: str
    price: float
    ram_gb: int
    ssd_gb: int
    delivery_days: int
    warranty_years: int


class AnalysisRequest(BaseModel):
    requirements: Requirements
    vendors: List[Vendor]


@app.get("/")
def home():
    return {
        "message": "PROCURE.AI backend is running!",
        "status": "success"
    }


@app.post("/analyze")
def analyze(data: AnalysisRequest):
    results = []

    for vendor in data.vendors:
        failures = []

        if vendor.ram_gb < data.requirements.min_ram_gb:
            failures.append(
                f"RAM {vendor.ram_gb}GB is below the "
                f"{data.requirements.min_ram_gb}GB minimum"
            )

        if vendor.ssd_gb < data.requirements.min_ssd_gb:
            failures.append("SSD capacity is below minimum")

        if vendor.price > data.requirements.max_price:
            failures.append("Price exceeds the budget")

        if vendor.delivery_days > data.requirements.max_delivery_days:
            failures.append("Delivery exceeds the deadline")

        if vendor.warranty_years < data.requirements.min_warranty_years:
            failures.append("Warranty is below minimum")

        results.append({
            "vendor": vendor.name,
            "price": vendor.price,
            "eligible": len(failures) == 0,
            "status": "Eligible" if not failures else "Not eligible",
            "reasons": failures
        })

    eligible = [v for v in results if v["eligible"]]

    # Rank eligible vendors by lowest price.
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

    return {
        "total_vendors": len(results),
        "eligible_count": len(eligible),
        "ranking_method": "Lowest price among eligible vendors",
        "results": results
    }
