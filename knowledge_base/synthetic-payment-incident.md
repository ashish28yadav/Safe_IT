# Synthetic Incident: Payment Provider Timeout

**Document ID:** ops-synthetic-payment-incident
**Service:** payment-service
**Incident category:** dependency
**Document type:** synthetic_incident

## Symptoms
Example symptom: payment timeouts increased shortly after a provider latency change in the test scenario.

## Root cause
Synthetic example only: the simulated upstream provider exceeded its response budget while local service resource metrics were normal.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: The responder compared provider latency, payment error codes, and correlation IDs, then confirmed that retries were bounded and the circuit breaker was active.
4. Record observations and owners before proposing a change.

## Resolution procedure
The synthetic response was to escalate and use an approved provider failover procedure only after dependency health was confirmed. No real customer incident or payment record is represented.

## Verification steps
The simulated provider latency returned to baseline and the payment error rate stayed below threshold during the observation window.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
