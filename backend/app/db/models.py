
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ProcurementRun(Base):
    __tablename__ = "procurement_runs"

    run_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    requirements: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    vendor_records: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
    )
    evaluation_results: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
    )
    ranked_vendors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
    )
    selected_vendor: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    approval_decision: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    errors: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
        nullable=False,
    )
    event: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    reviewer: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
