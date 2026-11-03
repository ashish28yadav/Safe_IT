# Payment Duplicate Request Investigation

**Document ID:** ops-payment-idempotency
**Service:** payment-service
**Incident category:** correctness
**Document type:** runbook

## Symptoms
Customers or synthetic test callers observe repeated payment attempts after client retries.

## Root cause
An ambiguous timeout may cause a caller to retry without reusing its idempotency key, or a downstream response may be delayed.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Trace one correlation ID across API and provider logs; compare idempotency keys and request fingerprints; inspect retry timing and duplicate suppression counters.
4. Record observations and owners before proposing a change.

## Resolution procedure
Preserve ledger and event data. Do not delete or edit payment records. Escalate any suspected duplicate settlement to the payment owner and follow the approved reconciliation process.

## Verification steps
Confirm duplicate suppression counters and request outcomes; validate that the simulator reports one logical payment per idempotency key.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
