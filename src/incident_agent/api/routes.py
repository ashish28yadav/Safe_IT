"""Versioned, read-only infrastructure inspection routes."""

from enum import StrEnum

from fastapi import APIRouter, Depends, HTTPException, Query

from incident_agent.api.dependencies import get_infrastructure
from incident_agent.api.schemas import (RecoveryResponse, ServiceDetail, ServiceLog, ServiceLogs,
                                        ServiceMetrics, ServiceSummary)
from incident_agent.simulator.environment import InfrastructureManager

router = APIRouter(prefix="/api/v1", tags=["Infrastructure v1"])


class LogLevelFilter(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def _not_found(service_name: str, exc: ValueError) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Unknown service '{service_name}'.")


@router.get("/services", response_model=list[ServiceSummary], summary="List simulated services")
def list_services(infrastructure: InfrastructureManager = Depends(get_infrastructure)) -> list[ServiceSummary]:
    return [ServiceSummary(service_name=name, status=infrastructure.read_status(name),
                           healthy=infrastructure.telemetry(name)["healthy"])
            for name in infrastructure.list_services()]


@router.get("/services/{service_name}", response_model=ServiceDetail, summary="Get service details")
def get_service(service_name: str, infrastructure: InfrastructureManager = Depends(get_infrastructure)) -> ServiceDetail:
    try:
        telemetry = infrastructure.telemetry(service_name)
    except ValueError as exc:
        raise _not_found(service_name, exc) from exc
    telemetry["service_name"] = infrastructure.resolve_service_name(service_name)
    return ServiceDetail.model_validate(telemetry)


@router.get("/services/{service_name}/metrics", response_model=ServiceMetrics, summary="Get service metrics")
def get_metrics(service_name: str, infrastructure: InfrastructureManager = Depends(get_infrastructure)) -> ServiceMetrics:
    try:
        metrics = infrastructure.query_metrics(service_name)
    except ValueError as exc:
        raise _not_found(service_name, exc) from exc
    metrics["service_name"] = infrastructure.resolve_service_name(service_name)
    return ServiceMetrics.model_validate(metrics)


@router.get("/services/{service_name}/logs", response_model=ServiceLogs, summary="Search service logs")
def get_logs(
    service_name: str,
    level: LogLevelFilter | None = Query(default=None, description="Filter by log severity."),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum records to return."),
    search: str | None = Query(default=None, max_length=200, description="Case-insensitive message/error search."),
    infrastructure: InfrastructureManager = Depends(get_infrastructure),
) -> ServiceLogs:
    try:
        logs = infrastructure.search_logs(service_name, search or "")
    except ValueError as exc:
        raise _not_found(service_name, exc) from exc
    if level is not None:
        logs = [entry for entry in logs if entry["level"] == level.value]
    selected = [ServiceLog.model_validate(entry) for entry in logs[-limit:]]
    return ServiceLogs(service_name=infrastructure.resolve_service_name(service_name), count=len(selected), logs=selected)


@router.get("/services/{service_name}/recovery", response_model=RecoveryResponse, summary="Inspect service recovery")
def get_recovery(service_name: str, infrastructure: InfrastructureManager = Depends(get_infrastructure)) -> RecoveryResponse:
    try:
        telemetry = infrastructure.telemetry(service_name)
        recovered = infrastructure.verify_recovery(service_name)
    except ValueError as exc:
        raise _not_found(service_name, exc) from exc
    canonical_name = infrastructure.resolve_service_name(service_name)
    return RecoveryResponse(service_name=canonical_name, status=telemetry["status"],
                            healthy=telemetry["healthy"], recovered=recovered,
                            active_faults=sorted(infrastructure.services[canonical_name].active_failures),
                            verification="verified" if recovered else "faults_active_or_service_unhealthy")
