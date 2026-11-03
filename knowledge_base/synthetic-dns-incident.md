# Synthetic Incident: Dependency Name Resolution

**Document ID:** ops-synthetic-dns-incident
**Service:** general
**Incident category:** network
**Document type:** synthetic_incident

## Symptoms
Example symptom: a simulated service could not resolve its configured dependency name.

## Root cause
Synthetic example only: a test resolver returned intermittent lookup failures after a configuration change.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: The responder compared resolver status and affected service telemetry, then confirmed the failure occurred before connection establishment.
4. Record observations and owners before proposing a change.

## Resolution procedure
The synthetic response escalated a resolver configuration correction to its owner. No public hosts were queried.

## Verification steps
The configured dependency name resolved consistently and connection attempts succeeded in simulation.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
