"""Persisted incident investigation API; requests execute synchronously."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from incident_agent.agent.investigation.llm import LLMConfigurationError, LLMProviderError
from incident_agent.agent.investigation.service import (
    IncidentStateConflict, InvestigationRunError, InvestigationService,
)
from incident_agent.api.dependencies import get_investigation_service
from incident_agent.api.investigation_schemas import (
    InvestigationCancelResponse, InvestigationEvidenceResponse,
    InvestigationReportResponse, InvestigationResponse, InvestigationStartRequest,
    InvestigationTimelineResponse,
)

router = APIRouter(prefix="/api/v1/investigations", tags=["Investigations v1"])
logger = logging.getLogger(__name__)


@router.post("", response_model=InvestigationResponse, status_code=status.HTTP_201_CREATED,
             summary="Run an evidence-based investigation for an existing incident")
def start_investigation(request: InvestigationStartRequest,
                        service: InvestigationService = Depends(get_investigation_service)) -> InvestigationResponse:
    try:
        result = service.investigate(request.incident_id, use_llm=request.use_llm)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IncidentStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvestigationRunError as exc:
        status_code = 503 if exc.cause_type in {"LLMProviderError", "TimeoutError"} else 500
        raise HTTPException(
            status_code=status_code,
            detail={"message": "Investigation failed", "investigation_id": exc.investigation_id},
        ) from exc
    except (LLMProviderError, TimeoutError, RuntimeError) as exc:
        logger.warning("Investigation could not complete: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Investigation could not complete") from exc
    except Exception as exc:
        logger.exception("Unexpected investigation failure")
        raise HTTPException(status_code=500, detail="Investigation failed") from exc
    return InvestigationResponse(**result)


def _get_or_404(investigation_id: str, service: InvestigationService) -> dict:
    result = service.get(investigation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Investigation was not found")
    return result


@router.get("/{investigation_id}", response_model=InvestigationResponse,
            summary="Get investigation execution status")
def get_investigation(investigation_id: str,
                      service: InvestigationService = Depends(get_investigation_service)) -> InvestigationResponse:
    return InvestigationResponse(**_get_or_404(investigation_id, service))


@router.get("/{investigation_id}/report", response_model=InvestigationReportResponse,
            summary="Get the structured investigation report")
def get_investigation_report(investigation_id: str,
                             service: InvestigationService = Depends(get_investigation_service)) -> InvestigationReportResponse:
    result = _get_or_404(investigation_id, service)
    if result["report"] is None:
        raise HTTPException(status_code=409, detail="Investigation report is not complete")
    return InvestigationReportResponse.model_validate(result["report"])


@router.get("/{investigation_id}/evidence", response_model=InvestigationEvidenceResponse,
            summary="Get collected investigation evidence")
def get_investigation_evidence(investigation_id: str,
                               service: InvestigationService = Depends(get_investigation_service)) -> InvestigationEvidenceResponse:
    result = _get_or_404(investigation_id, service)
    return InvestigationEvidenceResponse(investigation_id=investigation_id, evidence=result["evidence"])


@router.get("/{investigation_id}/timeline", response_model=InvestigationTimelineResponse,
            summary="Get investigation node execution timeline")
def get_investigation_timeline(investigation_id: str,
                               service: InvestigationService = Depends(get_investigation_service)) -> InvestigationTimelineResponse:
    events = service.timeline(investigation_id)
    if events is None:
        raise HTTPException(status_code=404, detail="Investigation was not found")
    return InvestigationTimelineResponse(investigation_id=investigation_id, events=events)


@router.post("/{investigation_id}/cancel", response_model=InvestigationCancelResponse,
             status_code=status.HTTP_202_ACCEPTED, summary="Request cooperative investigation cancellation")
def cancel_investigation(investigation_id: str,
                         service: InvestigationService = Depends(get_investigation_service)) -> InvestigationCancelResponse:
    result = _get_or_404(investigation_id, service)
    if result["status"] != "RUNNING" or not service.cancel(investigation_id):
        raise HTTPException(status_code=409, detail="Investigation is not currently cancellable")
    return InvestigationCancelResponse(
        investigation_id=investigation_id, status="CANCEL_REQUESTED",
        detail="Cancellation will be applied at the next graph node boundary.",
    )
