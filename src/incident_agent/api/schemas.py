"""Pydantic response schemas for the public infrastructure API."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ServiceStatusResponse(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    RESTARTING = "RESTARTING"


class HealthResponse(BaseModel):
    status: str
    simulator_ready: bool
    registered_services: int
    mode: str


class ServiceSummary(BaseModel):
    service_name: str
    status: ServiceStatusResponse
    healthy: bool


class ServiceLog(BaseModel):
    timestamp: str
    level: str
    service_name: str
    message: str
    correlation_id: str
    error_details: str | None = None


class ServiceDetail(ServiceSummary):
    model_config = ConfigDict(extra="ignore")

    cpu_utilization: float
    memory_utilization: float
    request_count: int
    request_rate: float
    error_count: int
    error_rate: float
    latency_ms: float
    response_latency_ms: float
    backlog: int
    active_connections: int
    max_connections: int
    connection_pool_utilization: float
    start_time: str
    uptime_seconds: int
    availability: float
    logs: list[ServiceLog]


class ServiceMetrics(BaseModel):
    service_name: str
    status: ServiceStatusResponse
    cpu_utilization: float
    memory_utilization: float
    request_count: int
    request_rate: float
    error_count: int
    error_rate: float
    latency_ms: float
    response_latency_ms: float
    active_connections: int | None = None
    max_connections: int | None = None
    connection_pool_utilization: float | None = None
    connection_limit: int | None = None


class ServiceLogs(BaseModel):
    service_name: str
    count: int
    logs: list[ServiceLog]


class RecoveryResponse(BaseModel):
    service_name: str
    status: ServiceStatusResponse
    healthy: bool
    recovered: bool
    active_faults: list[str]
    verification: str
