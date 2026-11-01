"""Shared typed models for API, workflow, and simulator boundaries."""

from typing import Literal

from pydantic import BaseModel, Field

ServiceName = Literal["payment", "authentication", "notification", "postgres"]


class IncidentRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=4000)
    service: ServiceName
    scenario: str | None = None
    approved: bool = False


class ActionProposal(BaseModel):
    action: Literal["restart_service", "clear_notification_backlog", "recycle_db_connections"]
    target: ServiceName
    reason: str


class ActionResult(BaseModel):
    status: Literal["blocked", "approval_required", "applied"]
    detail: str


class IncidentResult(BaseModel):
    incident_id: str
    title: str
    diagnosis: str
    evidence: list[str]
    retrieved_runbooks: list[str]
    proposed_action: ActionProposal | None
    action_result: ActionResult | None

