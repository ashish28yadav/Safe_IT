"""Validated input and normalized incident data contracts."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IncidentSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    MITIGATING = "MITIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class AlertType(StrEnum):
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    ERROR_RATE = "ERROR_RATE"
    RESOURCE_DEGRADATION = "RESOURCE_DEGRADATION"
    HIGH_LATENCY = "HIGH_LATENCY"
    DATABASE_CONNECTIONS = "DATABASE_CONNECTIONS"
    MONITORING_ALERT = "MONITORING_ALERT"


class RawAlert(BaseModel):
    """Untrusted monitoring payload accepted by the ingestion boundary."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    incident_id: str | None = Field(default=None, min_length=1, max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=8000)
    service_name: str = Field(min_length=1, max_length=100)
    severity: IncidentSeverity | None = None
    alert_type: AlertType
    created_at: datetime | None = None
    affected_services: list[str] = Field(default_factory=list, max_length=20)
    metrics_snapshot: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, min_length=1, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("service_name")
    @classmethod
    def normalize_service_token(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @field_validator("created_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("created_at must include a timezone")
        return value.astimezone(timezone.utc) if value is not None else value

    @field_validator("metrics_snapshot", mode="before")
    @classmethod
    def normalize_metric_names(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized: dict[Any, Any] = {}
        for name, metric in value.items():
            key = name.strip().lower() if isinstance(name, str) else name
            if key in normalized:
                raise ValueError(f"Duplicate metric after normalization: {key}")
            normalized[key] = metric
        return normalized

    @model_validator(mode="after")
    def validate_payload_limits_and_metrics(self) -> "RawAlert":
        try:
            encoded_size = len(self.model_dump_json().encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Alert payload must contain JSON-compatible values") from exc
        if encoded_size > 64_000:
            raise ValueError("Alert payload exceeds the 64 KB limit")
        if len(self.metadata) > 50 or len(json.dumps(self.metadata, ensure_ascii=True)) > 16_000:
            raise ValueError("metadata exceeds supported size limits")
        if len(self.metrics_snapshot) > 32:
            raise ValueError("metrics_snapshot supports at most 32 metrics")
        for name, value in self.metrics_snapshot.items():
            if not isinstance(name, str) or len(name) > 80:
                raise ValueError("Metric names must be strings up to 80 characters")
            if isinstance(value, (dict, list)):
                raise ValueError(f"Metric '{name}' must be a scalar value")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"Metric '{name}' must be finite")
            if name in {"cpu_utilization", "memory_utilization"} and isinstance(value, (int, float)) and not 0 <= value <= 100:
                raise ValueError(f"Metric '{name}' must be between 0 and 100")
            if name == "error_rate" and isinstance(value, (int, float)) and not 0 <= value <= 1:
                raise ValueError("Metric 'error_rate' must be between 0 and 1")
            if name in {"request_count", "error_count", "latency_ms", "active_connections", "max_connections"} and isinstance(value, (int, float)) and value < 0:
                raise ValueError(f"Metric '{name}' cannot be negative")
        if "max_connections" in self.metrics_snapshot and "active_connections" in self.metrics_snapshot:
            if self.metrics_snapshot["active_connections"] > self.metrics_snapshot["max_connections"]:
                raise ValueError("active_connections cannot exceed max_connections")
        return self


class Incident(BaseModel):
    """Normalized incident record stored in the local registry."""

    model_config = ConfigDict(extra="forbid")

    incident_id: str
    title: str
    description: str
    service_name: str
    severity: IncidentSeverity
    alert_type: AlertType
    status: IncidentStatus
    created_at: datetime
    updated_at: datetime
    affected_services: list[str]
    metrics_snapshot: dict[str, Any]
    correlation_id: str
    metadata: dict[str, Any]
    related_incident_ids: list[str] = Field(default_factory=list)

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Incident timestamps must include a timezone")
        return value.astimezone(timezone.utc)


class IncidentStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: IncidentStatus


class IncidentHistoryEntry(BaseModel):
    timestamp: datetime
    event: str
    previous_status: IncidentStatus | None = None
    new_status: IncidentStatus | None = None
    related_incident_id: str | None = None
    details: str | None = None


class IncidentHistory(BaseModel):
    incident_id: str
    entries: list[IncidentHistoryEntry]

