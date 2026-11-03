# CPU Saturation Triage

**Document ID:** ops-cpu-saturation
**Service:** payment-service
**Incident category:** capacity
**Document type:** runbook

## Symptoms
CPU remains near saturation with increased response latency or queueing.

## Root cause
Traffic growth, inefficient work, retries, or a hot code path may be contributing.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Compare CPU by process with request rate, error rate, and latency; inspect recent releases and repeated log patterns; check upstream retry volume.
4. Record observations and owners before proposing a change.

## Resolution procedure
Do not scale or restart automatically. Coordinate capacity or rollback changes with the service owner and verify available host capacity.

## Verification steps
Confirm CPU drops below the alert threshold and latency and error rate recover under representative simulator traffic.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
