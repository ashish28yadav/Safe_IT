"""SQLAlchemy tables for incidents, lifecycle events, and relationships."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String,
                        Text, TypeDecorator)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class UTCDateTime(TypeDecorator[datetime]):
    """Store UTC timestamps portably and restore timezone awareness from SQLite."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Database timestamps must be timezone-aware")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


class IncidentRow(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_service_severity", "service_name", "severity"),
        Index("ix_incidents_created_at", "created_at"),
    )

    incident_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    payload_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    affected_services: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    metrics_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, nullable=False)


class IncidentHistoryRow(Base):
    __tablename__ = "incident_history"
    __table_args__ = (Index("ix_incident_history_incident_timestamp", "incident_id", "timestamp"),)

    history_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incidents.incident_id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    event: Mapped[str] = mapped_column(String(40), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    related_incident_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)


class IncidentCorrelationRow(Base):
    __tablename__ = "incident_correlations"
    __table_args__ = (
        CheckConstraint("left_incident_id < right_incident_id", name="ck_correlation_order"),
    )

    left_incident_id: Mapped[str] = mapped_column(
        ForeignKey("incidents.incident_id", ondelete="CASCADE"), primary_key=True
    )
    right_incident_id: Mapped[str] = mapped_column(
        ForeignKey("incidents.incident_id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class InvestigationRow(Base):
    """Durable investigation status and the latest JSON-safe graph snapshot."""

    __tablename__ = "investigations"

    investigation_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incidents.incident_id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    completion_time: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    state_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    errors_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class InvestigationTimelineRow(Base):
    __tablename__ = "investigation_timeline"
    __table_args__ = (Index("ix_investigation_timeline_id_timestamp", "investigation_id", "timestamp"),)

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(
        ForeignKey("investigations.investigation_id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    step: Mapped[str] = mapped_column(String(80), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
