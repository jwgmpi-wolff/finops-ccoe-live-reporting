---
name: "Deploy FinOps Copilot"
description: "Deploy the FinOps live-reporting app and companion Microsoft 365 Copilot agent to a selected tenant."
argument-hint: "tenant=<tenant-id> subscription=<subscription-id-or-auto> location=<azure-region> live-app=<globally-unique-name> agent-api=<existing-url-or-deploy-new> publisher=<organization> contact=<email> publish=<yes-or-no>"
agent: "agent"
---

Deploy this repository's FinOps CCoE live-reporting app and Microsoft 365 Copilot agent end to end using the customization values in my request.

Use this repository's `m365-agent` package and bounded `/api/agent/reports/{domain}` routes. Do not copy generated environments, packages, credentials, or implementation files from another repository.

Requirements:

1. Treat the requested tenant as authoritative. Start read-only: verify both Git worktrees, tools, Azure CLI identity, Agents Toolkit identity, tenant, and enabled subscriptions. Stop before resource changes if the identity cannot access that tenant.
2. Use the requested subscription or ask me to select one when automatic discovery is ambiguous. Show the effective tenant, account, and subscription before deployment.
3. Create or select a tenant-owned Entra application for delegated Azure Resource Manager access. Configure the live App Service URL as a Single-page application redirect URI and the Teams OAuth redirect URI `https://teams.microsoft.com/api/platform/v1.0/oAuthRedirect`. Grant delegated `https://management.azure.com/user_impersonation` permission.
4. Deploy this FastAPI app with `deploy-azure.ps1`, passing the public Entra client ID and tenant authority. Confirm `https://<live-app>.azurewebsites.net/api/health` returns healthy.
5. Confirm the deployed API health and `/api/agent/reports/{domain}` contract. Point the Copilot package at the public HTTPS URL for this deployment.
6. Follow `m365-agent/README.md` and run `m365-agent/build-package.ps1` with target-tenant OAuth, API, publisher, and contact values.
7. Pause only for administrator authentication, consent, or secret entry that Microsoft requires in a secure UI or terminal. Never request, display, log, save, package, or pass a secret through Copilot Chat or command arguments. Resume using public IDs only.
8. Build and validate the exact generated ZIP with Agents Toolkit. Inspect it for the selected tenant authority, compatible agent API host, Teams app ID, OAuth registration ID, zero unresolved build placeholders, preserved Adaptive Card runtime expressions, and no credentials.
9. When `publish=yes`, provision/update the Developer Portal app, rebuild after Teams app ID assignment, validate again, publish to the tenant catalog, and verify availability. Use Teams Admin Center upload only as the documented fallback.
10. Smoke test both surfaces: browser OAuth and `/api/health` for live reporting, then Microsoft 365 Copilot OAuth plus one live bounded report for a subscription visible to the test user. Azure RBAC must remain the authorization boundary.
11. Report each stage as PASS, FAIL, or BLOCKED with non-secret evidence. Do not claim skipped or blocked deployment as successful.
12. Do not commit tenant-local environment files, deployment ZIPs, tokens, IDs, URLs, or credentials. Commit source and generic documentation only when explicitly requested.

At completion, return the repository revision, target tenant/account/subscription, live-reporting and agent API URL, public Entra/Teams/OAuth IDs, validation and publication results, smoke-test evidence, remaining manual actions, and cleanup/redeployment instructions.