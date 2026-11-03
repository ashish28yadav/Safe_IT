"""Configurable deterministic severity classification rules."""

from dataclasses import dataclass

from .models import AlertType, IncidentSeverity, RawAlert


@dataclass(frozen=True)
class SeverityThresholds:
    critical_error_rate: float = 0.30
    high_error_rate: float = 0.15
    degraded_resource_percent: float = 85.0
    degraded_latency_ms: float = 1000.0


class SeverityClassifier:
    def __init__(self, thresholds: SeverityThresholds | None = None) -> None:
        self.thresholds = thresholds or SeverityThresholds()

    def classify(self, alert: RawAlert) -> IncidentSeverity:
        metrics = alert.metrics_snapshot
        if (alert.alert_type == AlertType.SERVICE_UNAVAILABLE
                or metrics.get("service_available") is False):
            return IncidentSeverity.CRITICAL
        error_rate = metrics.get("error_rate")
        if isinstance(error_rate, (int, float)):
            if error_rate > self.thresholds.critical_error_rate:
                return IncidentSeverity.CRITICAL
            if error_rate > self.thresholds.high_error_rate:
                return IncidentSeverity.HIGH
        resource_values = (metrics.get("cpu_utilization"), metrics.get("memory_utilization"))
        if any(isinstance(value, (int, float)) and value >= self.thresholds.degraded_resource_percent
               for value in resource_values):
            return IncidentSeverity.MEDIUM
        latency = metrics.get("latency_ms")
        if isinstance(latency, (int, float)) and latency >= self.thresholds.degraded_latency_ms:
            return IncidentSeverity.MEDIUM
        return alert.severity or IncidentSeverity.LOW
