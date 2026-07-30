# One-Request Live Reporting and Copilot Deployment

Open this repository in VS Code and start GitHub Copilot Chat in **Agent** mode. Run:

```text
/deploy-finops-copilot tenant=<target-tenant-id> subscription=auto location=eastus live-app=<globally-unique-app-name> agent-api=deploy-new publisher="<organization-name>" contact=<support-email> publish=yes
```

The workspace prompt deploys two distinct surfaces from this repository:

1. This repository's interactive FastAPI live-reporting application.
2. The bounded agent API routes and Microsoft 365 package in `m365-agent`.

The browser and agent API routes have different contracts. The prompt validates the bounded `/api/agent/reports/{domain}` route before packaging or publication.

Microsoft administrator sign-in, consent, and secret entry remain interactive security boundaries. Enter secrets only in the Microsoft Entra or Developer Portal interface when prompted. Never paste a secret into Copilot Chat.

The workflow reports deployment, health, package validation, publication, and live smoke testing independently as PASS, FAIL, or BLOCKED.