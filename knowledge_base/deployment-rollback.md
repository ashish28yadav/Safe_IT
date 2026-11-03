# Safe Deployment Rollback Procedure

**Document ID:** ops-deployment-rollback
**Service:** general
**Incident category:** deployment
**Document type:** runbook

## Symptoms
A service regression starts immediately after a deployment or configuration change.

## Root cause
The current release may introduce a defect or incompatible dependency behavior.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Compare incident start time with release events; identify affected version and blast radius; confirm a known-good artifact and rollback compatibility; consult the service owner.
4. Record observations and owners before proposing a change.

## Resolution procedure
Rollback is a change requiring authorized approval. Preserve incident evidence and database compatibility; never run destructive migration reversal without a reviewed recovery plan.

## Verification steps
Verify deployed version, service health, error/latency metrics, and downstream compatibility after the approved rollback.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
