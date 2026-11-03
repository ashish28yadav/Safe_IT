# Cross-Service Correlation ID Troubleshooting

**Document ID:** ops-correlation-ids
**Service:** general
**Incident category:** observability
**Document type:** runbook

## Symptoms
Related errors appear across services but cannot be tied to one request path.

## Root cause
A correlation ID may be missing, regenerated, or omitted at an asynchronous boundary.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Select a synthetic request and follow its correlation ID across service logs; identify the first missing hop; check message headers and log-field normalization.
4. Record observations and owners before proposing a change.

## Resolution procedure
Use synthetic identifiers only in examples and avoid copying sensitive payloads into logs. Do not alter production telemetry settings from an incident session.

## Verification steps
Verify a new synthetic request retains one correlation ID across all expected service boundaries.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
