"""Public Pydantic request and response models for investigations."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from incident_agent.agent.investigation.models import Evidence, InvestigationReport


class InvestigationStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str = Field(min_length=1, max_length=100)
    use_llm: bool = False


class InvestigationResponse(BaseModel):
    investigation_id: str
    incident_id: str
    status: Literal["RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
    start_time: str
    completion_time: str | None = None
    errors: list[str] = Field(default_factory=list)


class InvestigationReportResponse(InvestigationReport):
    pass


class InvestigationEvidenceResponse(BaseModel):
    investigation_id: str
    evidence: list[Evidence]


class InvestigationTimelineResponse(BaseModel):
    investigation_id: str
    events: list[dict[str, str]]


class InvestigationCancelResponse(BaseModel):
    investigation_id: str
    status: Literal["CANCEL_REQUESTED"]
    detail: str
