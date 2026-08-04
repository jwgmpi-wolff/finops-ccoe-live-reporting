# FinOps CCoE Live Reporting

Live, multi-tenant Azure FinOps reporting with Entra/CLI auth, subscription discovery, domain-specific analytics, and multi-format exports.

## Deploy Buttons

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fjerrywolff_microsoft%2Ffinops-ccoe-live-reporting%2Fmain%2Finfra%2Fazuredeploy.json)
[![Deploy Local](https://img.shields.io/badge/Deploy-Local-2ea44f?logo=powershell&logoColor=white)](deploy-local.ps1)

Note: this repository is private due Enterprise Managed User policy. The Deploy-to-Azure button works for users/accounts with repository access.

## UI Sample Screenshots

### 0. Live UI Capture (Authentication and Context)
Real browser capture from the running application showing authentication status, context load, and tenant/subscription discovery controls.

![Live UI authentication sample](docs/screenshots/ui-auth-live.png)

### 1. Dashboard Overview
Shows the top-level UI layout including authentication controls, tenant/subscription scope selection, filters, and report actions.

![Dashboard overview](docs/screenshots/dashboard-overview.svg)

### 2. AI Token Tracking Results
Shows a representative live run for the AI token tracking domain with summary counters and result table preview.

![AI token results](docs/screenshots/ai-token-results.svg)

### 3. Export and Deployment Panel
Shows the export capabilities and deployment workflow highlights used by this project.

![Exports and deployment](docs/screenshots/exports-and-deploy.svg)

## Key Features

1. Live-only reporting pipeline (no mock data).
2. Tenant and subscription discovery after sign-in.
3. 16 FinOps reporting domains, including AI token tracking.
4. Data enrichment for opaque IDs and quality scoring.
5. Export support for CSV, PDF, PPTX, and SQLite.
6. Strict live validation mode for trust gating.
7. Clear authentication context switching and CLI reauth support.

## Tech Stack

1. FastAPI backend.
2. Pydantic models.
3. Azure REST APIs via httpx.
4. Browser UI with HTML/CSS/vanilla JavaScript.
5. Export generation with CSV, fpdf2, python-pptx, sqlite3.

## Project Layout

1. `app/main.py`: API routes, auth helpers, export endpoints.
2. `app/models.py`: report domains and schemas.
3. `app/services/azure_live.py`: Azure API connectors and query logic.
4. `app/services/reporting.py`: domain orchestration and recommendations.
5. `app/services/enrichment.py`: enrichment and quality scoring.
6. `app/services/exporters.py`: CSV/PDF/PPTX/SQLite export builders.
7. `app/static/app.js`: frontend behavior and report execution flow.
8. `deploy-local.ps1`: one-command local run.
9. `desktop_launcher.py` and `FinOpsCCoE.spec`: Windows desktop application entry point and package definition.
10. `build-windows.ps1` and `installer/FinOpsCCoE.iss`: reproducible Windows application and installer build.
11. `deploy-function.ps1`: Linux Flex Consumption Function App deployment and verification.
12. `deploy-azure.ps1`: legacy App Service provisioning + source deployment.
13. `infra/azuredeploy.json`: ARM template for the App Service Deploy-to-Azure button.

## Install on Windows

Install the generated `dist\installer\FinOpsCCoE-Setup.exe`, then launch **FinOps CCoE Live Reporting** from the Start menu. The application starts a local service on `http://127.0.0.1:8010` and opens the report in the default browser.

Prerequisites for live Azure data:

1. Azure CLI installed and signed in with `az login`, or `FINOPS_ENTRA_CLIENT_ID` configured for browser OAuth.
2. Azure RBAC access to the tenants and subscriptions being reported. The application does not elevate the signed-in user.

Exports from the installed application are written to `%LOCALAPPDATA%\FinOpsCCoE\exports`.

Build the Windows application and per-user installer from source:

```powershell
.\build-windows.ps1
```

The script creates an isolated `.build-venv`, runs the tests, builds the Application Control-compatible application folder at `dist\FinOpsCCoE`, and packages it as `dist\installer\FinOpsCCoE-Setup.exe`. Inno Setup 6 is installed with `winget` when it is not already available. Use `-SkipInstaller` to build only the application folder.

## Quick Start (Local)

```powershell
./deploy-local.ps1
```

Manual run:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Open: `http://127.0.0.1:8010`

## Deploy to Azure Functions (Flex Consumption)

Prerequisites:

1. Azure CLI and Azure Functions Core Tools on `PATH`.
2. Python 3.11 with the project dependencies installed.
3. An Azure sign-in with permission to create the resource group, storage account, and Function App in the explicit target subscription.

```powershell
az login
.\deploy-function.ps1 `
   -SubscriptionId "<subscription-id>" `
   -TenantId "<tenant-id>" `
   -ResourceGroup "rg-finops-functions" `
   -Location "eastus" `
   -FunctionAppName "finops-reporting-<unique-suffix>"
```

The script validates the active tenant and subscription, runs the tests, creates or reuses a Linux Python 3.11 Flex Consumption Function App and deployment storage, publishes with a remote build, and verifies HTTPS health.

Verify after deployment:

```powershell
Invoke-RestMethod "https://<function-app-name>.azurewebsites.net/api/health"
Start-Process "https://<function-app-name>.azurewebsites.net/api/run_finops_report"
```

The HTTP application uses the caller's delegated Azure permissions for live data access. Before production use, configure Function App authentication and appropriate network controls for your organization; do not expose reporting endpoints more broadly than intended.

To remove a dedicated deployment and all resources created in its resource group:

```powershell
az group delete --name "rg-finops-functions" --subscription "<subscription-id>"
```

Omit `-TenantId` only when the active Azure CLI tenant has already been independently verified. The script intentionally does not infer a subscription or tenant.

## Deploy to Azure (Legacy App Service)

```powershell
./deploy-azure.ps1 -ResourceGroup rg-finops-live -Location eastus -AppName finops-live-reporting-demo
```

What the script does:

1. Validates Azure CLI login.
2. Creates/updates resource group.
3. Creates Linux App Service plan.
4. Creates/updates Python web app.
5. Configures startup command and app settings.
6. Performs zip deployment of the project.

## Environment Configuration

1. `FINOPS_ENTRA_CLIENT_ID` (optional): enables browser OAuth path.
2. If not set, Azure CLI session login is still supported in the UI.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_api.py
```

## Full Regenerate Prompt (GitHub Copilot)

Use this prompt in GitHub Copilot Chat to regenerate the entire project from scratch:

```text
You are a senior cloud architect + full-stack engineer. Build a production-ready Azure FinOps CCoE Reporting System from scratch.

Objective:
Create a reporting platform that uses only live tenant data, supports Entra login with tenant selection, discovers subscriptions dynamically, allows report focus by one/many/all subscriptions, and separates reports by FinOps area with strong filtering and exports.

Non-negotiable requirements:
1. Live data only.
2. No cached data for analysis outputs.
3. No mock/hardcoded/hallucinated report values in runtime.
4. All report fields must be meaningful and human-identifiable.
5. If any query returns only GUID/resourceId/objectId, enrich it by resolving to the real resource/object metadata (name, type, group, subscription, region, tags, owner when available).
6. Never display unknown, N/A padding, or blank placeholders unless explicitly marked as not returned by source API, with source + timestamp.
7. Add export support for PDF, PPTX, CSV, and SQLite.
8. Multi-tenant flow must require user sign-in and explicit tenant selection before data pull.
9. Subscription selector must include discovered subscriptions + Select All.
10. Every report must show data freshness timestamp, source system, tenant, subscription scope, and query execution time.

Primary user flow:
1. User opens app.
2. User authenticates with Microsoft Entra ID.
3. App lists accessible tenants.
4. User selects tenant.
5. App discovers subscriptions for that tenant.
6. User selects one/many/all subscriptions.
7. User selects reporting area/domain.
8. User applies filters and runs report.
9. App shows results with recommendation signals.
10. User exports result to PDF/PPTX/CSV/SQLite.

Reporting domains:
1. Spend Visibility
2. Budget and Forecasting
3. Optimization (Rightsizing)
4. Reservations
5. Savings Plans
6. Savings Potential
7. Reservations Potential
8. Anomaly Detection
9. Governance
10. Tag Compliance
11. Chargeback and Showback
12. Architecture Efficiency
13. Sustainability
14. AI FinOps
15. AI Token Tracking
16. Idle and Waste Detection

For each domain, implement:
1. KPIs/metrics.
2. Query logic against live Azure sources.
3. Recommendations section (actionable items).
4. Filters relevant to domain.
5. Export handlers.

Azure data sources to integrate (live):
1. Azure Cost Management
2. Azure Resource Graph
3. Azure Advisor recommendations
4. Azure Policy compliance states
5. Reservations utilization/coverage
6. Savings Plans utilization/coverage
7. Management Groups metadata
8. Activity Logs
9. Azure Monitor metrics
10. Log Analytics (optional)
11. Azure Carbon Optimization / Sustainability APIs (if available)
12. Azure OpenAI / Foundry usage metrics for AI FinOps (if enabled)

Required filters (global):
1. Date range
2. Tenant
3. Subscription (single/multi/all)
4. Management group
5. Resource group
6. Service/resource type
7. Region
8. Tag key/value
9. Environment
10. Cost center
11. Recommendation severity/impact
12. Actionable-only toggle

Data quality and enrichment rules:
1. Build a normalization layer with strict schema validation.
2. Build an enrichment layer to resolve identifiers:
   - subscriptionId -> subscription name
   - resourceId -> parsed resource metadata
   - principal/object ids -> display name when permitted
3. Detect and suppress low-value records that contain only opaque identifiers with no enrichable business context.
4. Add a data quality score and unresolved fields count per report execution.
5. Keep an audit trail of source API calls and row counts per source.

Security and access:
1. Use Entra OAuth2/OIDC.
2. Use least-privilege scopes for ARM/Graph/Cost endpoints.
3. Respect user RBAC; do not overreach permissions.
4. No secret hardcoding; use secure configuration.
5. Include tenant boundary checks to prevent cross-tenant leakage.

Exports:
1. CSV export with flat normalized fields.
2. PDF export with executive summary + key charts + findings.
3. PPTX export with summary and tables.
4. SQLite export with relational tables:
   - report_runs
   - report_rows
   - recommendations
   - source_audit
   - enrichment_audit

Deployment and operations requirements:
1. Include deploy-local.ps1 to bootstrap and run locally.
2. Include deploy-azure.ps1 to provision and deploy to Azure App Service.
3. Include infra/azuredeploy.json and a Deploy-to-Azure button in README.
4. Include screenshots under docs/screenshots and reference them in README.
5. Include tests and clear onboarding instructions.

Strict validation gate:
- Fail report execution if live source connectivity is unavailable and strict-live mode is enabled.
- Display explicit error instead of stale fallback.
- Reject output if more than 5 percent of key business fields are unresolved after enrichment.

Now implement this end-to-end in code, scaffolding all needed files, wiring dependencies, adding tests, and providing complete run + deploy instructions.
```

## License

This project is provided as-is for internal enablement and engineering acceleration.
