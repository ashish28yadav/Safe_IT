# Synthetic Incident: Notification Queue Growth

**Document ID:** ops-synthetic-notification-incident
**Service:** notification-service
**Incident category:** queue
**Document type:** synthetic_incident

## Symptoms
Example symptom: oldest-message age increased while simulated delivery throughput fell.

## Root cause
Synthetic example only: a downstream rate limit reduced the notification consumer rate.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: The responder compared enqueue/consume rates, queue age, retry counts, and provider response codes before changing throughput.
4. Record observations and owners before proposing a change.

## Resolution procedure
The synthetic response restored consumer health and allowed a controlled drain within the provider limit. No messages were purged.

## Verification steps
Queue depth and oldest-message age trended down with no increase in duplicate delivery.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
