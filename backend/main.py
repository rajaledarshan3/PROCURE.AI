from fastapi.middleware.cors import CORSMiddleware
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from langgraph.types import Command
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.agent.graph import procurement_graph
from app.db.checkpointer import close_checkpointer, init_checkpointer
from app.db.database import SessionLocal, init_db
from app.db.models import AuditEvent, ProcurementRun
from app.services.constraint_engine import evaluate_vendor, rank_vendors
from app.services.dynamic_constraints import (
    evaluate_constraints,
    validate_constraints,
)
from app.services.procurement_templates import (
    get_template,
    list_templates,
)
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_checkpointer()
    try:
        yield
    finally:
        close_checkpointer()


app = FastAPI(
    title="PROCURE.AI",
    description="Agentic AI Procurement System",
    version="0.4.0",
    lifespan=lifespan,
)

# CORS: allow the Vite frontend on ports 5173 and 5174.


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "https://procureai-dur7lfd3b-cognitive-x.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        openapi_version="3.0.3",
    )

    upload_schema = schema["components"]["schemas"].get(
        "Body_upload_quotations_upload_quotations_post"
    )

    if upload_schema:
        upload_schema["properties"]["files"] = {
            "type": "array",
            "title": "Files",
            "items": {
                "type": "string",
                "format": "binary",
            },
        }

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi
app.openapi_version = "3.0.3"


# -------------------------
# DATABASE HELPERS
# -------------------------

def save_audit_event(
    run_id: str,
    event: str,
    reviewer: str | None = None,
    notes: str | None = None,
    details: dict | None = None,
) -> None:
    with SessionLocal() as session:
        session.add(
            AuditEvent(
                run_id=run_id,
                event=event,
                reviewer=reviewer,
                notes=notes,
                details=details,
            )
        )
        session.commit()


def get_audit_events(run_id: str) -> list[dict]:
    with SessionLocal() as session:
        statement = (
            select(AuditEvent)
            .where(AuditEvent.run_id == run_id)
            .order_by(AuditEvent.id)
        )
        records = session.scalars(statement).all()

        return [
            {
                "id": record.id,
                "event": record.event,
                "reviewer": record.reviewer,
                "notes": record.notes,
                "details": record.details,
                "created_at": (
                    record.created_at.isoformat()
                    if record.created_at
                    else None
                ),
            }
            for record in records
        ]


def get_run_record(run_id: str) -> ProcurementRun | None:
    with SessionLocal() as session:
        return session.get(ProcurementRun, run_id)


def update_run_record(
    run_id: str,
    *,
    status: str,
    evaluation_results: list[dict[str, Any]],
    ranked_vendors: list[dict[str, Any]],
    selected_vendor: dict[str, Any] | None,
    approval_decision: dict[str, Any] | None,
    errors: list[str],
) -> None:
    with SessionLocal() as session:
        record = session.get(ProcurementRun, run_id)

        if record is None:
            raise ValueError("Procurement run was not found.")

        record.status = status
        record.evaluation_results = evaluation_results
        record.ranked_vendors = ranked_vendors
        record.selected_vendor = selected_vendor
        record.approval_decision = approval_decision
        record.errors = errors
        session.commit()


def graph_config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


# -------------------------
# REQUEST MODELS
# -------------------------

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
    """Send `requirements` (laptop fields) OR `constraints` (any category)."""

    requirements: Requirements | None = None
    constraints: list[dict[str, Any]] | None = None
    vendors: list[dict[str, Any]] = Field(min_length=1)

    @model_validator(mode="after")
    def exactly_one_rule_source(self):
        if (self.requirements is None) == (not self.constraints):
            raise ValueError(
                "Send either 'requirements' or a non-empty 'constraints' "
                "list, not both and not neither."
            )
        return self


class ApprovalRequest(BaseModel):
    approved: bool
    reviewer: str = Field(min_length=1, max_length=100)
    notes: str = Field(default="", max_length=1000)

# -------------------------
# DYNAMIC CONSTRAINT ENDPOINT
# -------------------------

class DynamicEvaluationRequest(BaseModel):
    constraints: list[dict[str, Any]] = Field(min_length=1)
    vendors: list[dict[str, Any]] = Field(min_length=1)

@app.get("/templates")
def get_procurement_templates():
    return {"templates": list_templates()}


@app.get("/templates/{template_id}")
def get_procurement_template(template_id: str):
    template = get_template(template_id)

    if template is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown procurement template: {template_id}",
        )

    return {"id": template_id.lower(), **template}
@app.post("/evaluate-dynamic")
def evaluate_dynamic(data: DynamicEvaluationRequest):
    errors = validate_constraints(data.constraints)

    if errors:
        raise HTTPException(
            status_code=422,
            detail={"errors": errors},
        )

    results = []

    for vendor in data.vendors:
        result = evaluate_constraints(vendor, data.constraints)
        results.append({
            "vendor": vendor,
            **result,
        })

    return {
        "status": "success",
        "vendors_evaluated": len(results),
        "results": results,
    }
# -------------------------
# BASIC ENDPOINTS
# -------------------------

@app.get("/")
def home():
    return {
        "message": "PROCURE.AI backend is running!",
        "status": "success",
        "version": app.version,
    }


@app.get("/health")
def health():
    try:
        with SessionLocal() as session:
            session.execute(select(1))

        return {"status": "healthy", "database": "connected"}

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable.",
        ) from exc


# -------------------------
# DETERMINISTIC VENDOR ANALYSIS
# -------------------------

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


# -------------------------
# START PROCUREMENT WORKFLOW
# -------------------------

@app.post("/runs", status_code=201)
def create_run(data: ProcurementRunRequest):
    run_id = str(uuid4())

    if data.constraints is not None:
        # Universal mode: any product category, rules come from the request.
        constraint_errors = validate_constraints(data.constraints)

        if constraint_errors:
            raise HTTPException(
                status_code=422,
                detail={"errors": constraint_errors},
            )

        vendor_records = data.vendors
        requirements_snapshot = {"constraints": data.constraints}
        initial_state = {
            "requirements": requirements_snapshot,
            "constraints": data.constraints,
            "vendor_records": vendor_records,
            "errors": [],
        }
    else:
        # Legacy mode: fixed laptop requirements and vendor fields.
        try:
            vendor_records = [
                Vendor.model_validate(vendor).model_dump()
                for vendor in data.vendors
            ]
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=[
                    {"loc": list(error["loc"]), "msg": error["msg"]}
                    for error in exc.errors()
                ],
            ) from exc

        requirements_snapshot = data.requirements.model_dump()
        initial_state = {
            "requirements": data.requirements.model_dump(
                exclude={"quantity"}
            ),
            "vendor_records": vendor_records,
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

    if approval_required:
        status = "pending"

    evaluation_results = result.get("evaluation_results", [])
    ranked_vendors = result.get("ranked_vendors", [])
    selected_vendor = result.get("selected_vendor")
    approval_decision = result.get("approval_decision")
    errors = result.get("errors", [])

    try:
        with SessionLocal() as session:
            session.add(
                ProcurementRun(
                    run_id=run_id,
                    status=status,
                    requirements=requirements_snapshot,
                    vendor_records=vendor_records,
                    evaluation_results=evaluation_results,
                    ranked_vendors=ranked_vendors,
                    selected_vendor=selected_vendor,
                    approval_decision=approval_decision,
                    errors=errors,
                )
            )

            session.add(
                AuditEvent(
                    run_id=run_id,
                    event="procurement_analysis_started",
                    details={
                        "total_vendors": len(data.vendors),
                        "eligible_vendors": sum(
                            1
                            for vendor in ranked_vendors
                            if vendor.get("eligible")
                        ),
                    },
                )
            )

            if approval_required:
                session.add(
                    AuditEvent(
                        run_id=run_id,
                        event="recommendation_pending_review",
                        details={"selected_vendor": selected_vendor},
                    )
                )

            session.commit()

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not persist procurement run and audit events.",
        ) from exc

    return {
        "run_id": run_id,
        "status": status,
        "total_vendors": len(data.vendors),
        "evaluation_results": evaluation_results,
        "ranked_vendors": ranked_vendors,
        "approval_required": approval_required,
        "ai_explanations": result.get("ai_explanations"),
        "ai_warnings": result.get("ai_warnings", []),
        "errors": errors,
    }


# -------------------------
# HUMAN APPROVAL / REJECTION
# -------------------------

@app.post("/runs/{run_id}/approval")
def submit_approval(run_id: str, decision: ApprovalRequest):
    run = get_run_record(run_id)

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Procurement run not found.",
        )

    if run.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Run cannot be reviewed in status '{run.status}'.",
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

    try:
        with SessionLocal() as session:
            record = session.get(ProcurementRun, run_id)

            if record is None:
                raise HTTPException(
                    status_code=404,
                    detail="Procurement run not found.",
                )

            record.status = status
            record.evaluation_results = result.get(
                "evaluation_results", []
            )
            record.ranked_vendors = result.get("ranked_vendors", [])
            record.selected_vendor = result.get("selected_vendor")
            record.approval_decision = result.get("approval_decision")
            record.errors = result.get("errors", [])

            session.add(
                AuditEvent(
                    run_id=run_id,
                    event=status,
                    reviewer=decision.reviewer,
                    notes=decision.notes,
                    details={
                        "approved": decision.approved,
                        "selected_vendor": result.get("selected_vendor"),
                    },
                )
            )

            session.commit()

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not persist the approval decision.",
        ) from exc

    return {
        "run_id": run_id,
        "status": status,
        "selected_vendor": result.get("selected_vendor"),
        "approval_decision": result.get("approval_decision"),
        "audit_log": get_audit_events(run_id),
    }


# -------------------------
# GET PROCUREMENT RUN
# -------------------------

@app.get("/runs/{run_id}")
def get_run(run_id: str):
    run = get_run_record(run_id)

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="Procurement run not found.",
        )

    try:
        audit_log = get_audit_events(run_id)
        snapshot = procurement_graph.get_state(graph_config(run_id))
        state = snapshot.values or {}

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve procurement workflow state.",
        ) from exc

    return {
        "run_id": run.run_id,
        "status": run.status,
        "requirements": run.requirements,
        "total_vendors": len(run.vendor_records),
        "evaluation_results": run.evaluation_results,
        "ranked_vendors": run.ranked_vendors,
        "selected_vendor": run.selected_vendor,
        "approval_decision": run.approval_decision,
        "errors": run.errors,
        "workflow_checkpoint_available": bool(state),
        "ai_explanations": state.get("ai_explanations"),
        "ai_warnings": state.get("ai_warnings", []),
        "audit_log": audit_log,
    }


# -------------------------
# QUOTATION FILE UPLOAD
# -------------------------

@app.post("/upload-quotations")
async def upload_quotations(
    files: Annotated[list[UploadFile], File()],
):
    from app.tools.parser import SUPPORTED_FORMATS, parse_quotation

    parsed_files = []

    with tempfile.TemporaryDirectory() as temp_dir:
        for uploaded_file in files:
            filename = Path(uploaded_file.filename or "").name
            suffix = Path(filename).suffix.lower()

            try:
                if not filename or suffix not in SUPPORTED_FORMATS:
                    raise HTTPException(
                        status_code=415,
                        detail=(
                            f"Unsupported file format: "
                            f"{suffix or 'unknown'}"
                        ),
                    )

                content = await uploaded_file.read()

                if not content:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Uploaded file is empty: {filename}",
                    )

                temp_path = Path(temp_dir) / f"{uuid4().hex}{suffix}"
                temp_path.write_bytes(content)

                try:
                    parsed = parse_quotation(temp_path)
                    parsed["source_file"] = filename
                    parsed_files.append(parsed)

                except HTTPException:
                    raise

                except Exception as exc:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Could not parse {filename}: {exc}",
                    ) from exc

            finally:
                await uploaded_file.close()

    return {
        "uploaded_files": len(parsed_files),
        "files": parsed_files,
    }
    

