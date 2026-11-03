# Authentication Key Rollover Failure

**Document ID:** ops-authentication-key-rollover
**Service:** authentication-service
**Incident category:** configuration
**Document type:** runbook

## Symptoms
New tokens fail validation after a signing key rotation while older tokens may still validate.

## Root cause
Issuer and verifier key sets may have changed at different times, or key metadata may not have propagated.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Compare key identifiers and validity windows without copying secret key material; inspect issuer/verifier configuration versions and refresh timestamps; check clock synchronization.
4. Record observations and owners before proposing a change.

## Resolution procedure
Never paste private keys or bearer tokens into incident notes. Roll back or republish key metadata only through the approved security change process.

## Verification steps
Use non-sensitive synthetic tokens to verify both current and rollover-window keys; confirm audit events and validation errors normalize.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
