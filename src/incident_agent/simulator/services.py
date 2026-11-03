"""Deterministic service state and structured simulator telemetry."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class ServiceStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    RESTARTING = "RESTARTING"


class LogLevel(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class StructuredLog:
    timestamp: str
    level: LogLevel
    service_name: str
    message: str
    correlation_id: str
    error_details: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {"timestamp": self.timestamp, "level": self.level.value,
                "service_name": self.service_name, "message": self.message,
                "correlation_id": self.correlation_id, "error_details": self.error_details}


@dataclass
class ServiceState:
    name: str
    healthy: bool = True
    latency_ms: int = 40
    error_rate: float = 0.0
    backlog: int = 0
    logs: list[StructuredLog] = field(default_factory=list)
    status: ServiceStatus = ServiceStatus.HEALTHY
    cpu_utilization: float = 15.0
    memory_utilization: float = 30.0
    request_count: int = 1000
    error_count: int = 0
    start_time: str = field(default_factory=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat())
    uptime_seconds: int = 86400
    active_failures: set[str] = field(default_factory=set)
    active_connections: int = 12
    max_connections: int = 100

    def add_log(self, message: str, level: LogLevel = LogLevel.INFO,
                error_details: str | None = None, correlation_id: str = "sim-000001") -> StructuredLog:
        entry = StructuredLog(datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(), level,
                              self.name, message, correlation_id, error_details)
        self.logs.append(entry)
        return entry

    def telemetry(self) -> dict[str, Any]:
        return {"service": self.name, "service_name": self.name, "healthy": self.healthy,
                "status": self.status.value, "cpu_utilization": self.cpu_utilization,
                "memory_utilization": self.memory_utilization, "request_count": self.request_count,
                "request_rate": self.request_count / 60, "error_count": self.error_count,
                "error_rate": self.error_rate, "latency_ms": self.latency_ms,
                "response_latency_ms": self.latency_ms, "backlog": self.backlog,
                "active_connections": self.active_connections, "max_connections": self.max_connections,
                "connection_pool_utilization": self.active_connections / self.max_connections,
                "start_time": self.start_time, "uptime_seconds": self.uptime_seconds,
                "availability": 1.0 if self.healthy else 0.0,
                "logs": [entry.as_dict() for entry in self.logs]}


class PaymentService(ServiceState):
    def __init__(self) -> None: super().__init__("payment-service")


class AuthenticationService(ServiceState):
    def __init__(self) -> None: super().__init__("authentication-service")


class NotificationService(ServiceState):
    def __init__(self) -> None: super().__init__("notification-service")


class PostgresSimulator(ServiceState):
    """In-memory PostgreSQL facade; it never opens a database connection."""

    def __init__(self) -> None:
        super().__init__("postgres-database")
        self.connection_limit = self.max_connections
        self.add_log("database ready")

    def telemetry(self) -> dict[str, Any]:
        result = super().telemetry()
        result.update(service="postgres", connection_limit=self.connection_limit)
        return result
