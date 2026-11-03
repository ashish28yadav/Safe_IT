# Service Network Timeout Troubleshooting

**Document ID:** ops-network-timeouts
**Service:** general
**Incident category:** network
**Document type:** runbook

## Symptoms
Calls between simulated services exceed timeouts or fail intermittently.

## Root cause
Routing, packet loss, connection churn, or an overloaded dependency can cause timeouts.

## Diagnostic steps
1. Capture the alert timestamp, affected service, and correlation ID; compare with the service's recent baseline.
2. Use service metrics and structured logs to distinguish local resource pressure from a dependency or configuration problem.
3. Follow scenario checks: Compare connection, TLS, and response timing; test only approved in-process simulator health interfaces; correlate failures by destination and time; inspect retry counts.
4. Record observations and owners before proposing a change.

## Resolution procedure
Do not probe external hosts or alter firewall/network policy. Keep retries bounded and escalate suspected network changes to the platform owner.

## Verification steps
Verify the affected dependency path and application requests recover without elevated retries.

## Safety warnings
All actions here are human guidance. Confirm scope, authorization, and rollback plan before any state-changing operation. Never use these procedures to access real infrastructure from this simulator, expose credentials, delete data, or bypass security controls.
