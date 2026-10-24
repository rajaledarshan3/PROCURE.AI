
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from langgraph.types import Command

from app.agent.graph import procurement_graph
from app.services.constraint_engine import evaluate_vendor, rank_vendors


app = FastAPI(
    title="PROCURE.AI",
    description="Agentic AI Procurement System",
    version="0.2.0",
)

# Demo storage only. Runs and audit events are not durable across restarts.
RUNS: dict[str, dict[str, Any]] = {}


class Requirements(BaseModel):
    quantity: int = Field(default=50, gt=0)
    min_ram_gb: int = Field(default=16, ge=0)
    min_ssd_gb: int = Field(default=512, ge=0)
    max_price: float = Field(default=60000, gt=0)
    max_delivery_days: int = Field(default=15, gt=0)
    min_warranty_years: float = Field(default=3, ge=0)


class Vendor(BaseModel):
    name: str
    price: float = Field(gt=0)
    ram_gb: float = Field(ge=0)
    ssd_gb: float = Field(ge=0)
    delivery_days: int = Field(ge=0)
    warranty_years: float = Field(ge=0)


class AnalysisRequest(BaseModel):
    requirements: Requirements
    vendors: list[Vendor]


class ProcurementRunRequest(BaseModel):
    requirements: Requirements
    vendors: list[Vendor] = Field(min_length=1)


class ApprovalRequest(BaseModel):
    approved: bool
    reviewer: str = Field(min_length=1, max_length=100)
    notes: str = Field(default="", max_length=1000)


def graph_config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


@app.get("/")
def home():
    return {
        "message": "PROCURE.AI backend is running!",
        "status": "success",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/analyze")
def analyze(data: AnalysisRequest):
    results = [
        evaluate_vendor(data.requirements, vendor)
        for vendor in data.vendors
    ]
    rank_vendors(results)

    return {
        "total_vendors": len(results),
        "eligible_count": sum(
            1 for vendor in results if vendor["eligible"]
        ),
        "ranking_method": "Lowest price among eligible vendors",
        "results": results,
    }


@app.post("/runs", status_code=201)
def create_run(data: ProcurementRunRequest):
    run_id = str(uuid4())

    initial_state = {
        "requirements": data.requirements.model_dump(exclude={"quantity"}),
        "vendor_records": [
            vendor.model_dump() for vendor in data.vendors
        ],
        "errors": [],
    }

    try:
        result = procurement_graph.invoke(
            initial_state,
            config=graph_config(run_id),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Procurement analysis failed: {exc}",
        ) from exc

    interrupts = result.get("__interrupt__", [])
    approval_required = [
        item.value if hasattr(item, "value") else item
        for item in interrupts
    ]

    status = result.get("approval_status", "unknown")

    RUNS[run_id] = {
        "status": status,
        "audit_log": [
            {
                "event": "procurement_analysis_started",
                "run_id": run_id,
            }
        ],
    }

    if approval_required:
        RUNS[run_id]["status"] = "pending"
        RUNS[run_id]["audit_log"].append(
            {"event": "recommendation_pending_review"}
        )

    return {
        "run_id": run_id,
        "status": RUNS[run_id]["status"],
        "total_vendors": len(data.vendors),
        "evaluation_results": result.get("evaluation_results", []),
        "ranked_vendors": result.get("ranked_vendors", []),
        "approval_required": approval_required,
        "errors": result.get("errors", []),
    }


@app.post("/runs/{run_id}/approval")
def submit_approval(run_id: str, decision: ApprovalRequest):
    run = RUNS.get(run_id)

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Run not found in this server session.",
        )

    if run["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Run cannot be reviewed in status '{run['status']}'.",
        )

    try:
        result = procurement_graph.invoke(
            Command(
                resume={
                    "approved": decision.approved,
                    "reviewer": decision.reviewer,
                    "notes": decision.notes,
                }
            ),
            config=graph_config(run_id),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not resume approval workflow: {exc}",
        ) from exc

    status = result.get("approval_status", "unknown")
    run["status"] = status
    run["audit_log"].append(
        {
            "event": status,
            "reviewer": decision.reviewer,
            "notes": decision.notes,
        }
    )

    return {
        "run_id": run_id,
        "status": status,
        "selected_vendor": result.get("selected_vendor"),
        "approval_decision": result.get("approval_decision"),
        "audit_log": run["audit_log"],
    }


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    run = RUNS.get(run_id)

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Run not found in this server session.",
        )

    snapshot = procurement_graph.get_state(graph_config(run_id))
    state = snapshot.values or {}

    return {
        "run_id": run_id,
        "status": run["status"],
        "selected_vendor": state.get("selected_vendor"),
        "ranked_vendors": state.get("ranked_vendors", []),
        "approval_decision": state.get("approval_decision"),
        "audit_log": run["audit_log"],
    }
