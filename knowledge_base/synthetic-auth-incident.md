# Synthetic Incident: Authentication Key Metadata Delay

**Document ID:** ops-synthetic-auth-incident
**Service:** authentication-service
**Incident category:** configuration
**Document type:** synthetic_incident

## Symptoms
Example symptom: synthetic tokens signed with the newly active key were rejected by one simulated verifier.

## Root cause
Synthetic example only: key metadata refresh lagged behind the issuer rotation in a test environment.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: The responder compared non-secret key identifiers and configuration timestamps across issuer and verifier, then checked the simulated clock status.
4. Record observations and owners before proposing a change.

## Resolution procedure
The synthetic response used the approved key metadata refresh procedure. No private key or real user token is included.

## Verification steps
Synthetic valid and invalid token checks passed and the verifier recorded the expected key identifier.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
