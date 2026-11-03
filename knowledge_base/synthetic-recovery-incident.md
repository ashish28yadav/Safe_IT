# Synthetic Incident: Recovery Check Failed

**Document ID:** ops-synthetic-recovery-incident
**Service:** authentication-service
**Incident category:** recovery
**Document type:** synthetic_incident

## Symptoms
Example symptom: the process restarted successfully but the health verification continued to report an active latency fault.

## Root cause
Synthetic example only: the simulated restart cleared a crashed process but did not clear an independent dependency latency fault.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: The responder checked active fault state, latency metrics, and dependency logs instead of treating process status as proof of recovery.
4. Record observations and owners before proposing a change.

## Resolution procedure
The synthetic response kept the incident open and escalated the persistent dependency fault; no additional restart loop was initiated.

## Verification steps
Recovery was recorded only after the dependency fault was cleared in simulation and health metrics remained stable.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
