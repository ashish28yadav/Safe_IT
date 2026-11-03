"""Incident ingestion and management API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from incident_agent.api.dependencies import get_incident_registry
from incident_agent.incidents.models import (Incident, IncidentHistory, IncidentSeverity,
                                             IncidentStatus, IncidentStatusUpdate, RawAlert)
from incident_agent.incidents.registry import (DuplicateIncidentError, IncidentRegistry,
                                               IdempotencyConflictError, InvalidIncidentTransition)

router = APIRouter(prefix="/api/v1/incidents", tags=["Incidents"])


@router.post("", response_model=Incident, status_code=status.HTTP_201_CREATED,
             summary="Ingest a monitoring alert")
def create_incident(alert: RawAlert, registry: IncidentRegistry = Depends(get_incident_registry)) -> Incident:
    try:
        return registry.create(alert)
    except DuplicateIncidentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[Incident], summary="List and filter incidents")
def list_incidents(
    severity: IncidentSeverity | None = Query(default=None),
    service_name: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    registry: IncidentRegistry = Depends(get_incident_registry),
) -> list[Incident]:
    try:
        return registry.list(severity=severity, service_name=service_name, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{incident_id}", response_model=Incident, summary="Get an incident")
def get_incident(incident_id: str, registry: IncidentRegistry = Depends(get_incident_registry)) -> Incident:
    incident = registry.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' was not found.")
    return incident


@router.patch("/{incident_id}/status", response_model=Incident, summary="Update incident lifecycle status")
def update_incident_status(
    incident_id: str,
    update: IncidentStatusUpdate,
    registry: IncidentRegistry = Depends(get_incident_registry),
) -> Incident:
    try:
        return registry.update_status(incident_id, update.status)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidIncidentTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{incident_id}/history", response_model=IncidentHistory, summary="Get incident history")
def get_incident_history(
    incident_id: str, registry: IncidentRegistry = Depends(get_incident_registry)
) -> IncidentHistory:
    entries = registry.history(incident_id)
    if entries is None:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' was not found.")
    return IncidentHistory(incident_id=incident_id, entries=entries)
