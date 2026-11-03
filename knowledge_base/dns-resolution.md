# DNS Resolution Failure Runbook

**Document ID:** ops-dns-resolution
**Service:** general
**Incident category:** network
**Document type:** runbook

## Symptoms
Service logs report name resolution failures or connection attempts fail before reaching the dependency.

## Root cause
Resolver outage, stale records, search-domain configuration, or transient cache inconsistency may be involved.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Compare resolver error codes and timing; validate the expected service name through approved local configuration; check whether failures affect multiple services and inspect recent DNS changes.
4. Record observations and owners before proposing a change.

## Resolution procedure
Do not query arbitrary public domains or modify DNS records without ownership approval. Never put secrets in diagnostic commands.

## Verification steps
Verify expected names resolve consistently in the approved environment and dependent connection success returns.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
