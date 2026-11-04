"""Small, auditable nodes used by the read-only investigation graph."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from incident_agent.agent.investigation.llm import InvestigationLLMProvider
from incident_agent.agent.investigation.models import IncidentContext, InvestigationState
from incident_agent.agent.investigation.tools import ReadOnlyInfrastructureTools
from incident_agent.incidents.registry import IncidentRegistry
from incident_agent.retrieval.engine import RetrievalEngine


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _step(state: InvestigationState, name: str, detail: str) -> list[dict[str, str]]:
    steps = list(state.get("investigation_steps", []))
    steps.append({"step": name, "timestamp": _now(), "detail": detail[:500]})
    return steps


def _observation_id(investigation_id: str, kind: str, service: str) -> str:
    return f"obs-{investigation_id[:12]}-{kind}-{service}"


ALERT_CATEGORIES = {
    "SERVICE_UNAVAILABLE": "availability",
    "ERROR_RATE": "availability",
    "RESOURCE_DEGRADATION": "capacity",
    "HIGH_LATENCY": "performance",
    "DATABASE_CONNECTIONS": "database",
}
LOG_SEARCH_TERMS = frozenset({
    "error", "errors", "timeout", "timeouts", "connection", "pool", "failure", "failed",
    "unavailable", "exhausted", "crash", "latency", "dns", "queue",
})
SENSITIVE_TEXT = re.compile(
    r"(?i)\b(api[_-]?key|password|secret|token|authorization)\b(\s*[:=]\s*|\s+)([^\s,;]+)"
)
METRIC_FOCUS = {
    "SERVICE_UNAVAILABLE": ["status", "uptime_seconds", "availability", "error_rate"],
    "ERROR_RATE": ["error_rate", "error_count", "request_count", "latency_ms"],
    "RESOURCE_DEGRADATION": ["cpu_utilization", "memory_utilization", "status"],
    "HIGH_LATENCY": ["latency_ms", "error_rate", "request_rate"],
    "DATABASE_CONNECTIONS": ["active_connections", "max_connections", "connection_pool_utilization"],
    "MONITORING_ALERT": ["status", "cpu_utilization", "memory_utilization", "error_rate", "latency_ms"],
}


class InvestigationNodes:
    def __init__(self, registry: IncidentRegistry, tools: ReadOnlyInfrastructureTools,
                 retrieval: RetrievalEngine, provider: InvestigationLLMProvider | None = None) -> None:
        self.registry = registry
        self.tools = tools
        self.retrieval = retrieval
        self.provider = provider

    def validate_incident(self, state: InvestigationState) -> dict[str, Any]:
        incident = self.registry.get(state["incident_id"])
        if incident is None:
            raise KeyError(f"Incident '{state['incident_id']}' was not found")
        if incident.status.value == "CLOSED":
            raise ValueError("Closed incidents cannot be investigated")
        services = self.tools.canonical_services([incident.service_name, *incident.affected_services])
        context = IncidentContext(
            incident_id=incident.incident_id, title=incident.title, description=incident.description,
            service_name=incident.service_name, severity=incident.severity.value,
            alert_type=incident.alert_type.value, status=incident.status.value,
            created_at=incident.created_at.isoformat(), correlation_id=incident.correlation_id,
            affected_services=services, related_incident_ids=incident.related_incident_ids,
            metrics_snapshot=incident.metrics_snapshot,
            metadata=incident.metadata,
        ).model_dump(mode="json")
        start = state.get("start_time", _now())
        return {"incident_context": context, "affected_services": services,
                "investigation_status": "RUNNING", "start_time": start,
                "investigation_steps": _step(state, "validate_incident", "Incident and service scope validated")}

    def classify_incident(self, state: InvestigationState) -> dict[str, Any]:
        incident = state["incident_context"]
        category = ALERT_CATEGORIES.get(str(incident["alert_type"]), "operations")
        symptoms = [str(incident["title"]), str(incident["description"])]
        if state.get("use_llm"):
            if self.provider is None:
                raise RuntimeError("LLM-backed investigation is not configured")
            safe_metrics = {key: value for key, value in incident["metrics_snapshot"].items()
                            if key in set(METRIC_FOCUS.get(str(incident["alert_type"]), []))
                            | {"request_count", "error_count", "request_rate", "error_rate", "latency_ms",
                               "response_latency_ms", "active_connections", "max_connections",
                               "connection_pool_utilization", "backlog", "service_available"}}
            safe_incident = {
                "incident_id": incident["incident_id"],
                "title": SENSITIVE_TEXT.sub(r"\1\2[REDACTED]", str(incident["title"])),
                "description": SENSITIVE_TEXT.sub(r"\1\2[REDACTED]", str(incident["description"])),
                "service_name": incident["service_name"], "severity": incident["severity"],
                "alert_type": incident["alert_type"], "affected_services": incident["affected_services"],
                "metrics_snapshot": safe_metrics,
            }
            analysis = self.provider.analyze({"incident": safe_incident})
            result = analysis.result
            suggested_category = result.get("incident_category")
            suggested_symptoms = result.get("symptoms")
            if isinstance(suggested_category, str) and 0 < len(suggested_category) <= 80:
                category = suggested_category
            if isinstance(suggested_symptoms, list):
                symptoms = [str(item)[:300] for item in suggested_symptoms[:10] if isinstance(item, str)] or symptoms
            token_usage = analysis.token_usage or {}
            return {"incident_category": category, "symptoms": symptoms,
                    "relevant_metric_names": METRIC_FOCUS.get(str(incident["alert_type"]), []),
                    "log_search_patterns": sorted(LOG_SEARCH_TERMS),
                    "llm_analysis": result, "token_usage": token_usage,
                    "investigation_steps": _step(state, "classify_incident", "LLM suggestions accepted as unverified labels")}
        return {"incident_category": category, "symptoms": symptoms,
                "relevant_metric_names": METRIC_FOCUS.get(str(incident["alert_type"]), []),
                "log_search_patterns": sorted(LOG_SEARCH_TERMS),
                "investigation_steps": _step(state, "classify_incident", "Rule-based incident classification")}

    def retrieve_knowledge(self, state: InvestigationState) -> dict[str, Any]:
        context = state["incident_context"]
        query = f"{context['title']} {context['description']} {state.get('incident_category', '')}"
        response = self.retrieval.search(
            query[:2000], strategy="hybrid", top_k=5, candidate_count=15,
            service=str(context["service_name"]),
            category=ALERT_CATEGORIES.get(str(context["alert_type"])),
        )
        sources = [{
            "document_id": hit.document_id, "chunk_id": hit.chunk_id, "title": hit.title,
            "source": hit.source, "section": hit.section, "service": hit.service,
            "category": hit.category, "document_type": hit.document_type,
            "strategy": response.strategy, "rank": hit.rank, "content": hit.content,
        } for hit in response.results]
        return {"retrieved_documents": sources, "retrieved_sources": sources,
                "investigation_steps": _step(state, "retrieve_knowledge", f"Retrieved {len(sources)} attributed chunks")}

    def inspect_service_health(self, state: InvestigationState) -> dict[str, Any]:
        observations = []
        for service in state["affected_services"]:
            values = self.tools.inspect_status(service)
            observations.append({"observation_id": _observation_id(state["investigation_id"], "health", service),
                                 "observation_type": "service", "service_name": service,
                                 "observed_at": _now(), "values": values, "source": "simulator.read_status"})
        return {"service_observations": observations,
                "investigation_steps": _step(state, "inspect_service_health", f"Inspected {len(observations)} services")}

    def inspect_metrics(self, state: InvestigationState) -> dict[str, Any]:
        observations = []
        for service in state["affected_services"]:
            values = self.tools.inspect_metrics(service)
            observations.append({"observation_id": _observation_id(state["investigation_id"], "metrics", service),
                                 "observation_type": "metric", "service_name": service,
                                 "observed_at": _now(), "values": values, "source": "simulator.query_metrics"})
        return {"metric_observations": observations,
                "investigation_steps": _step(state, "inspect_metrics", f"Collected metrics for {len(observations)} services")}

    def inspect_logs(self, state: InvestigationState) -> dict[str, Any]:
        observations = []
        incident = state["incident_context"]
        text_sources = [str(incident.get("title", "")), str(incident.get("description", ""))]
        text_sources.extend(str(source.get("content", "")) for source in state.get("retrieved_sources", []))
        text_sources.append(str(incident.get("alert_type", "")))
        combined = " ".join(text_sources).casefold()
        queries = sorted(set(state.get("log_search_patterns", [])) | {
            term for term in LOG_SEARCH_TERMS if re.search(rf"\b{re.escape(term)}\b", combined)
        })
        for service in state["affected_services"]:
            logs_by_key = {}
            for query in queries[:12]:
                for entry in self.tools.inspect_logs(service, query):
                    key = (entry.get("timestamp"), entry.get("message"), entry.get("correlation_id"))
                    logs_by_key[key] = entry
            logs = list(logs_by_key.values())[:100]
            entries = logs or [None]
            for index, entry in enumerate(entries, 1):
                timestamp = entry.get("timestamp") if isinstance(entry, dict) else None
                observations.append({
                    "observation_id": f"{_observation_id(state['investigation_id'], 'log', service)}-{index:03d}",
                    "observation_type": "log", "service_name": service, "observed_at": timestamp,
                    "values": {"log": entry}, "source": "simulator.search_logs",
                })
        return {"log_observations": observations,
                "investigation_steps": _step(state, "inspect_logs", f"Searched logs for {len(observations)} services")}

    def correlate_evidence(self, state: InvestigationState) -> dict[str, Any]:
        evidence: list[dict[str, Any]] = []
        for collection in ("service_observations", "metric_observations", "log_observations"):
            for observation in state.get(collection, []):
                evidence.append({
                    "evidence_id": observation["observation_id"], "evidence_type": "simulator_observation",
                    "observation": _describe_observation(observation), "source": observation["source"],
                    "observed_at": observation.get("observed_at"), "related_service": observation["service_name"],
                    "supports_hypothesis": [], "contradicts_hypothesis": [],
                })
        dependencies = [{"observation_id": f"dep-{state['investigation_id']}-{service}",
                         "observation_type": "dependency", "service_name": service,
                         "observed_at": _now(), "values": self.tools.inspect_dependencies(service),
                         "source": "simulator.dependency_model"} for service in state["affected_services"]]
        for observation in dependencies:
            evidence.append({
                "evidence_id": observation["observation_id"], "evidence_type": "simulator_observation",
                "observation": _describe_observation(observation), "source": observation["source"],
                "observed_at": observation["observed_at"], "related_service": observation["service_name"],
                "supports_hypothesis": [], "contradicts_hypothesis": [],
            })
        correlated_sources = []
        for source_item in state.get("retrieved_sources", []):
            content = str(source_item.get("content", "")).casefold().replace("_", " ")
            matching_fields: list[str] = []
            related_observation_ids: list[str] = []
            for metric_observation in state.get("metric_observations", []):
                if metric_observation["service_name"] != source_item["service"]:
                    continue
                for field_name in metric_observation["values"]:
                    normalized_field = str(field_name).replace("_", " ").casefold()
                    if len(normalized_field) >= 4 and normalized_field in content:
                        matching_fields.append(str(field_name))
                        related_observation_ids.append(str(metric_observation["observation_id"]))
            item = {**source_item, "related_observation_ids": sorted(set(related_observation_ids)),
                    "matched_metric_fields": sorted(set(matching_fields))}
            correlated_sources.append(item)
            evidence.append({
                "evidence_id": item["chunk_id"], "evidence_type": "retrieved_reference",
                "observation": (
                    f"Reference material: {item['title']} — {item['section']}. "
                    f"Exact metric-name overlaps: {', '.join(item['matched_metric_fields']) or 'none'}. "
                    "Reference text is not proof of current conditions."
                ),
                "source": f"{item['document_id']}#{item['chunk_id']}", "observed_at": None,
                "related_service": item["service"], "supports_hypothesis": [],
                "contradicts_hypothesis": [],
            })
        evidence.append({
            "evidence_id": f"input-{state['incident_id']}", "evidence_type": "incident_input",
            "observation": f"Incident alert: {state['incident_context']['title']}",
            "source": f"incident:{state['incident_id']}", "observed_at": state["incident_context"]["created_at"],
            "related_service": state["incident_context"]["service_name"],
            "supports_hypothesis": [], "contradicts_hypothesis": [],
        })
        incident_metrics = state["incident_context"].get("metrics_snapshot", {})
        if isinstance(incident_metrics, dict):
            for field_name, value in incident_metrics.items():
                evidence.append({
                    "evidence_id": f"input-{state['incident_id']}-metric-{field_name}",
                    "evidence_type": "incident_input",
                    "observation": f"Alert-supplied metric {field_name}={value!r}; not independently verified.",
                    "source": f"incident:{state['incident_id']}/metrics_snapshot",
                    "observed_at": state["incident_context"]["created_at"],
                    "related_service": state["incident_context"]["service_name"],
                    "supports_hypothesis": [], "contradicts_hypothesis": [],
                })
        return {"evidence": evidence, "retrieved_sources": correlated_sources,
                "dependency_observations": dependencies,
                "investigation_steps": _step(state, "correlate_evidence", f"Correlated {len(evidence)} evidence records")}

    def generate_hypotheses(self, state: InvestigationState) -> dict[str, Any]:
        candidates: list[dict[str, Any]] = []
        for metric in state.get("metric_observations", []):
            values = metric["values"]
            service = metric["service_name"]
            cases = [
                ("database_connection_exhaustion", service == "postgres-database" and values.get("connection_pool_utilization", 0) >= 0.95,
                 "Database connection pool exhaustion", "Observed connection pool utilization is at least 95%.", "connection_pool_utilization"),
                ("high_cpu", values.get("cpu_utilization", 0) >= 90,
                 "CPU saturation", "Observed CPU utilization is at least 90%.", "cpu_utilization"),
                ("high_memory", values.get("memory_utilization", 0) >= 95,
                 "Memory exhaustion", "Observed memory utilization is at least 95%.", "memory_utilization"),
                ("high_error_rate", values.get("error_rate", 0) >= 0.3,
                 "Elevated HTTP error rate", "Observed error rate is at least 30%.", "error_rate"),
                ("high_latency", values.get("latency_ms", 0) >= 1000,
                 "High response latency", "Observed response latency is at least 1000 ms.", "latency_ms"),
                ("notification_backlog", service == "notification-service" and values.get("backlog", 0) > 1000,
                 "Notification queue backlog", "Observed notification backlog exceeds 1,000 items.", "backlog"),
            ]
            for key, matched, title, explanation, metric_name in cases:
                if matched:
                    evidence_id = str(metric["observation_id"])
                    candidates.append({"hypothesis_id": f"hyp-{key}-{service}", "title": title,
                                       "explanation": explanation, "supporting_evidence_ids": [evidence_id],
                                       "contradicting_evidence_ids": [], "confidence": "moderate",
                                       "verification_status": "supported"})
        for observation in state.get("service_observations", []):
            values = observation["values"]
            if not values.get("healthy"):
                candidates.append({"hypothesis_id": f"hyp-service-down-{observation['service_name']}",
                                   "title": f"Service unavailable: {observation['service_name']}",
                                   "explanation": "The simulator reports this service as unhealthy.",
                                   "supporting_evidence_ids": [observation["observation_id"]],
                                   "contradicting_evidence_ids": [], "confidence": "moderate",
                                   "verification_status": "supported"})
        llm_candidates = state.get("llm_analysis", {}).get("candidate_hypotheses", [])
        if isinstance(llm_candidates, list):
            for index, item in enumerate(llm_candidates[:3]):
                if isinstance(item, dict) and isinstance(item.get("title"), str) and isinstance(item.get("explanation"), str):
                    candidates.append({"hypothesis_id": f"hyp-model-{index + 1}",
                                       "title": item["title"][:160], "explanation": item["explanation"][:500],
                                       "supporting_evidence_ids": [], "contradicting_evidence_ids": [],
                                       "confidence": "low", "verification_status": "unverified"})
        candidates.sort(key=lambda item: (-len(item["supporting_evidence_ids"]), item["hypothesis_id"]))
        selected = candidates[:10]
        hypotheses_by_evidence: dict[str, list[str]] = {}
        contradictions_by_evidence: dict[str, list[str]] = {}
        for hypothesis in selected:
            for evidence_id in hypothesis["supporting_evidence_ids"]:
                hypotheses_by_evidence.setdefault(evidence_id, []).append(hypothesis["hypothesis_id"])
            hypothesis_key = str(hypothesis["hypothesis_id"]).removeprefix("hyp-")
            service = next((name for name in state["affected_services"]
                            if hypothesis_key.endswith(f"-{name}")), "")
            hypothesis_type = hypothesis_key.removesuffix(f"-{service}") if service else hypothesis_key
            relevant_terms = {
                "high_error_rate": ("error", "failure"), "high_latency": ("timeout", "latency"),
                "high_cpu": ("cpu", "saturation"), "high_memory": ("memory", "exhausted"),
                "database_connection_exhaustion": ("connection", "pool"),
                "notification_backlog": ("queue", "backlog"), "service": ("unavailable", "crash"),
                "service-down": ("unavailable", "crash"),
            }.get(hypothesis_type, ())
            contradictory_terms = {
                "high_error_rate": ("no errors", "error rate normal", "healthy"),
                "high_latency": ("latency normal", "low latency", "healthy"),
                "high_cpu": ("cpu normal", "cpu utilization normal"),
                "high_memory": ("memory normal", "memory utilization normal"),
                "database_connection_exhaustion": ("connections available", "pool healthy"),
                "notification_backlog": ("queue empty", "no backlog"),
                "service-down": ("service healthy", "service available"),
            }.get(hypothesis_type, ())
            for observation in state.get("log_observations", []):
                if observation["service_name"] != service:
                    continue
                entry = observation["values"].get("log")
                if not isinstance(entry, dict):
                    continue
                combined_log = (str(entry.get("message", "")) + " " +
                                str(entry.get("error_details") or "")).casefold()
                if entry.get("level") in {"ERROR", "CRITICAL", "WARNING"} and any(
                    term in combined_log for term in relevant_terms
                ):
                    if observation["observation_id"] not in hypothesis["supporting_evidence_ids"]:
                        hypothesis["supporting_evidence_ids"].append(observation["observation_id"])
                    hypotheses_by_evidence.setdefault(observation["observation_id"], []).append(
                        hypothesis["hypothesis_id"]
                    )
                if any(term in combined_log for term in contradictory_terms):
                    hypothesis["contradicting_evidence_ids"].append(observation["observation_id"])
                    if hypothesis["confidence"] == "moderate":
                        hypothesis["confidence"] = "low"
                    contradictions_by_evidence.setdefault(observation["observation_id"], []).append(
                        hypothesis["hypothesis_id"]
                    )
            metric_thresholds = {
                "high_cpu": ("cpu_utilization", 90), "high_memory": ("memory_utilization", 95),
                "high_error_rate": ("error_rate", 0.3), "high_latency": ("latency_ms", 1000),
                "database_connection_exhaustion": ("connection_pool_utilization", 0.95),
                "notification_backlog": ("backlog", 1000),
            }
            threshold = metric_thresholds.get(hypothesis_type)
            snapshot = state["incident_context"].get("metrics_snapshot", {})
            if threshold and isinstance(snapshot, dict):
                field_name, limit = threshold
                supplied = snapshot.get(field_name)
                if isinstance(supplied, (int, float)) and supplied < limit:
                    conflicting_id = f"input-{state['incident_id']}-metric-{field_name}"
                    hypothesis["contradicting_evidence_ids"].append(conflicting_id)
                    contradictions_by_evidence.setdefault(conflicting_id, []).append(hypothesis["hypothesis_id"])
                    if hypothesis["confidence"] == "moderate":
                        hypothesis["confidence"] = "low"
        evidence = [{**item,
                     "supports_hypothesis": hypotheses_by_evidence.get(item["evidence_id"], []),
                     "contradicts_hypothesis": contradictions_by_evidence.get(item["evidence_id"], [])}
                    for item in state.get("evidence", [])]
        return {"hypotheses": selected, "evidence": evidence,
                "investigation_steps": _step(state, "generate_hypotheses", f"Generated {len(candidates[:10])} evidence-linked hypotheses")}

    def assess_missing_evidence(self, state: InvestigationState) -> dict[str, Any]:
        missing = []
        if not state.get("log_observations") or not any(
            observation["values"].get("log") for observation in state["log_observations"]
        ):
            missing.append("No matching error or warning logs were available in the simulator.")
        missing.append("Simulator log search does not support filtering by the incident time window.")
        if any(item["values"].get("dependency_state") == "not_modelled"
               for item in state.get("dependency_observations", [])):
            missing.append("Dependency health is not modeled by the current simulator.")
        if not state.get("hypotheses"):
            missing.append("Available direct observations do not distinguish a root cause.")
        assessment = ("Direct observations support one or more candidate explanations; confidence is qualitative."
                      if state.get("hypotheses") else "Evidence is insufficient to identify a likely cause.")
        return {"missing_evidence": missing, "confidence_assessment": assessment,
                "recommended_actions": ["Review the cited observations and references.",
                                        "Collect the missing evidence before choosing a remediation."],
                "investigation_steps": _step(state, "assess_missing_evidence", f"Recorded {len(missing)} evidence gaps")}

    def generate_report(self, state: InvestigationState) -> dict[str, Any]:
        incident = IncidentContext.model_validate(state["incident_context"])
        observations = [*state.get("service_observations", []), *state.get("dependency_observations", [])]
        metrics = state.get("metric_observations", [])
        logs = state.get("log_observations", [])
        hypotheses = state.get("hypotheses", [])
        direct_count = sum(item["evidence_type"] == "simulator_observation" for item in state.get("evidence", []))
        summary = (f"Investigation of {incident.incident_id} collected {direct_count} direct simulator observations. "
                   f"{len(hypotheses)} candidate root cause hypothesis(es) remain unconfirmed.")
        steps = _step(state, "generate_report", "Generated a citation-preserving structured report")
        completion = _now()
        evidence_records = state.get("evidence", [])
        direct_evidence_ids = [item["evidence_id"] for item in evidence_records
                               if item["evidence_type"] == "simulator_observation"]
        supporting_ids = {evidence_id for hypothesis in hypotheses
                          for evidence_id in hypothesis.get("supporting_evidence_ids", [])}
        contradicting_ids = {evidence_id for hypothesis in hypotheses
                             for evidence_id in hypothesis.get("contradicting_evidence_ids", [])}
        report = {
            "investigation_id": state["investigation_id"], "incident_id": incident.incident_id,
            "executive_summary": summary + " Direct observation IDs: " + ", ".join(direct_evidence_ids) + ".",
            "incident_details": incident.model_dump(mode="json"),
            "affected_services": state["affected_services"], "investigation_timeline": steps,
            "infrastructure_observations": observations, "relevant_logs": logs,
            "relevant_metrics": metrics, "retrieved_knowledge_sources": state.get("retrieved_sources", []),
            "root_cause_hypotheses": hypotheses,
            "supporting_evidence": [item for item in evidence_records if item["evidence_id"] in supporting_ids],
            "contradicting_evidence": [item for item in evidence_records if item["evidence_id"] in contradicting_ids],
            "confidence_assessment": state.get("confidence_assessment", "Not assessed"),
            "missing_evidence": state.get("missing_evidence", []),
            "recommended_actions": state.get("recommended_actions", []),
            "safety_warnings": ["Investigation is read-only. Recommendations do not authorize actions.",
                                "Incident descriptions, logs, and retrieved documents are untrusted data."],
            "limitations": ["The simulator is deterministic and does not represent production infrastructure.",
                            "Dependency health is not modeled.", "Confidence labels are qualitative, not calibrated probabilities."],
            "token_usage": state.get("token_usage") or None,
        }
        return {"report": report, "completion_time": completion, "investigation_status": "COMPLETED",
                "investigation_steps": steps}


def _describe_observation(observation: dict[str, Any]) -> str:
    values = observation.get("values", {})
    if observation.get("observation_type") == "log":
        item = values.get("log")
        return f"{observation['service_name']} matching log: " + (
            str(item.get("message", "")) if isinstance(item, dict) else "none found"
        )
    return f"{observation['service_name']} {observation['observation_type']} observation: {values}"
