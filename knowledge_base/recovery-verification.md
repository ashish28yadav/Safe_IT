# Service Recovery Verification Checklist

**Document ID:** ops-recovery-verification
**Service:** general
**Incident category:** recovery
**Document type:** runbook

## Symptoms
A mitigation has been applied and responders need evidence that service behavior is stable.

## Root cause
A single successful health check may hide persistent faults, queue buildup, or dependency degradation.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Check service readiness and active fault state; compare error rate, latency, CPU, memory, pool usage, and queue age with baseline; inspect recent error logs.
4. Record observations and owners before proposing a change.

## Resolution procedure
Do not declare recovery based only on process restart or one green probe. Keep monitoring and preserve the incident record until the owner confirms stability.

## Verification steps
Observe multiple checks over the configured recovery window, verify dependent services, and record evidence and timestamp.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
