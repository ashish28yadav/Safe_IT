"""Serializable contracts for an incident investigation graph."""

from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field


class IncidentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str
    title: str
    description: str
    service_name: str
    severity: str
    alert_type: str
    status: str
    created_at: str
    correlation_id: str
    affected_services: list[str]
    related_incident_ids: list[str]
    metrics_snapshot: dict[str, object]
    metadata: dict[str, object]


class RetrievedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    chunk_id: str
    title: str
    source: str
    section: str
    service: str
    category: str
    document_type: str
    strategy: str
    rank: int = Field(ge=1)
    content: str
    related_observation_ids: list[str] = Field(default_factory=list)
    matched_metric_fields: list[str] = Field(default_factory=list)


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    observation_type: Literal["service", "metric", "log", "dependency"]
    service_name: str
    observed_at: str | None = None
    values: dict[str, object]
    source: str


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    evidence_type: Literal["simulator_observation", "retrieved_reference", "incident_input"]
    observation: str
    source: str
    observed_at: str | None = None
    related_service: str | None = None
    supports_hypothesis: list[str] = Field(default_factory=list)
    contradicts_hypothesis: list[str] = Field(default_factory=list)


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str
    title: str
    explanation: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["low", "moderate", "high"]
    verification_status: Literal["unverified", "supported", "contradicted"] = "unverified"


class InvestigationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investigation_id: str
    incident_id: str
    executive_summary: str
    incident_details: IncidentContext
    affected_services: list[str]
    investigation_timeline: list[dict[str, str]]
    infrastructure_observations: list[Observation]
    relevant_logs: list[Observation]
    relevant_metrics: list[Observation]
    retrieved_knowledge_sources: list[RetrievedSource]
    root_cause_hypotheses: list[Hypothesis]
    supporting_evidence: list[Evidence]
    contradicting_evidence: list[Evidence]
    confidence_assessment: str
    missing_evidence: list[str]
    recommended_actions: list[str]
    safety_warnings: list[str]
    limitations: list[str]
    token_usage: dict[str, int] | None = None


class InvestigationState(TypedDict, total=False):
    """LangGraph state contains JSON-compatible values only; no clients or secrets."""

    investigation_id: str
    incident_id: str
    incident_context: dict[str, object]
    affected_services: list[str]
    investigation_status: str
    investigation_steps: list[dict[str, str]]
    retrieved_documents: list[dict[str, object]]
    retrieved_sources: list[dict[str, object]]
    service_observations: list[dict[str, object]]
    metric_observations: list[dict[str, object]]
    log_observations: list[dict[str, object]]
    dependency_observations: list[dict[str, object]]
    hypotheses: list[dict[str, object]]
    evidence: list[dict[str, object]]
    missing_evidence: list[str]
    confidence_assessment: str
    recommended_actions: list[str]
    investigation_errors: list[str]
    token_usage: dict[str, int]
    start_time: str
    completion_time: str
    incident_category: str
    symptoms: list[str]
    relevant_metric_names: list[str]
    log_search_patterns: list[str]
    report: dict[str, object]
    use_llm: bool
    llm_analysis: dict[str, object]
    step_budget: int
