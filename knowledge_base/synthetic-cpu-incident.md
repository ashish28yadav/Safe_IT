# Synthetic Incident: CPU Saturation After Release

**Document ID:** ops-synthetic-cpu-incident
**Service:** payment-service
**Incident category:** capacity
**Document type:** synthetic_incident

## Symptoms
Example symptom: CPU and payment latency rose together after a simulated application release.

## Root cause
Synthetic example only: an inefficient request path increased per-request compute in the local test scenario.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: The responder correlated CPU, request rate, latency, and release version and checked that upstream retries had not amplified the load.
4. Record observations and owners before proposing a change.

## Resolution procedure
The synthetic response followed the approved rollback path; no automatic scaling or restart occurred.

## Verification steps
CPU and latency returned to baseline after the simulated release was rolled back.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
