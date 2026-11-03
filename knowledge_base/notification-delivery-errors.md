# Notification Delivery Error Spike

**Document ID:** ops-notification-delivery-errors
**Service:** notification-service
**Incident category:** dependency
**Document type:** runbook

## Symptoms
Delivery failures increase for one channel or downstream provider.

## Root cause
Provider outage, credentials/configuration rotation, or a new response contract may be involved.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Group failures by channel, provider, and response code; inspect bounded retry behavior and credential version metadata without exposing credentials; compare release history.
4. Record observations and owners before proposing a change.

## Resolution procedure
Do not print secrets or disable delivery validation. Escalate provider or credential updates through the owning team.

## Verification steps
Confirm provider responses recover, retry queues drain at a safe rate, and delivery receipts are consistent.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
