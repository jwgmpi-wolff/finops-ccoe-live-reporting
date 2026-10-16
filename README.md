# FinOps CCoE Live Reporting and Microsoft 365 Copilot Agent

A live-only Azure FinOps reporting platform and read-only Microsoft 365 Copilot declarative agent. The project discovers the signed-in user's tenants and subscriptions, queries Microsoft APIs within that user's Azure RBAC boundary, produces evidence-backed recommendations, and exports reports to CSV, PDF, PowerPoint, and SQLite.

## Download Windows Installer (AMD and Intel)

**[Download FinOpsCCoE-Setup.exe from jwgmpi-wolff](https://github.com/jwgmpi-wolff/finops-ccoe-live-reporting/releases/latest/download/FinOpsCCoE-Setup.exe)**

**[Download FinOpsCCoE-Setup.exe from jerrywolff_microsoft](https://github.com/jerrywolff_microsoft/finops-ccoe-live-reporting/releases/latest/download/FinOpsCCoE-Setup.exe)**

The same Windows x64 installer supports both AMD and Intel PCs. Download it from the repository your GitHub account can access, then run it to install. No Python installation or administrator access is required. Sign into GitHub before downloading private release assets to avoid a 404.

For portable downloads, checksums, and installation details, see [Download for Windows](#download-for-windows).

![Live UI authentication sample](docs/screenshots/ui-auth-live.png)

## Deploy Buttons

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fjerrywolff_microsoft%2Ffinops-ccoe-live-reporting%2Fmain%2Finfra%2Fazuredeploy.json)
[![Install on Windows x64 (AMD and Intel)](https://img.shields.io/badge/Install-Windows_x64_AMD_%26_Intel-0078d4?logo=windows&logoColor=white)](https://github.com/jwgmpi-wolff/finops-ccoe-live-reporting/releases/latest/download/FinOpsCCoE-Setup.exe)
[![Run locally](https://img.shields.io/badge/Run-Locally-2ea44f?logo=powershell&logoColor=white)](#run-locally)

## Visual Overview & Capability Diagrams

| Live Reporting & Idle Waste Detection | Result Inspection & Azure Handoff |
| :---: | :---: |
| ![Idle Waste Detection test fixture](docs/screenshots/report-scopes/idle_waste_detection.jpg) | ![Live result details sample](docs/screenshots/live-result-details.png) |
| *Live Idle Waste Detection report with KPI cards, savings by recommendation, impact breakdown, and category charts* | *Drilldown into individual findings with portal direct-links and metadata* |

| Live Tenant & Subscription Discovery | Export Artifact Formats |
| :---: | :---: |
| ![Live UI authentication sample](docs/screenshots/ui-auth-live.png) | ![Successful export sample](docs/screenshots/export-success.png) |
| *Live tenant/subscription discovery, filters, and 24 scope selections* | *Committed multi-format exports (CSV, PDF, PPTX, SQLite)* |

| Platform Architecture & Copilot Workflows | Mobile Responsive Layout |
| :---: | :---: |
| ![Dashboard overview](docs/screenshots/dashboard-overview.svg) | ![Mobile Idle Waste Detection test fixture](docs/screenshots/report-scopes/mobile-idle-waste-detection.jpg) |
| *Authentication boundary, query engine, and Copilot workflows* | *Mobile-optimized graph cards, drilldown tables, and touch controls* |

## Contents

- [Deploy Buttons](#deploy-buttons)
- [Visual Overview](#visual-overview--capability-diagrams)
- [Architecture](#architecture)
- [Features](#key-features)
- [Download for Windows](#download-for-windows)
- [Install on Windows](#install-on-windows)
- [Run locally](#run-locally)
- [Deploy to Azure Functions](#deploy-to-azure-functions-flex-consumption)
- [Build the Copilot agent](#build-the-microsoft-365-copilot-agent)
- [Reporting Scope Gallery](#reporting-scope-test-gallery)
- [Test](#testing)
- [Regenerate with GitHub Copilot](#full-regenerate-prompt-github-copilot)

## Screenshots

### Live dashboard

Real browser capture showing authentication, tenant and subscription discovery, report filters, export actions, and results.

![Live UI authentication sample](docs/screenshots/ui-auth-live.png)

### Result details

Sanitized live UI capture showing a clickable result record, resource metadata, and the Azure portal handoff. Placeholder identifiers are used in place of tenant data.

![Live result details sample](docs/screenshots/live-result-details.png)

### Successful export

Sanitized live UI capture showing export completion with the committed byte count and the available CSV, PDF, PowerPoint, and SQLite actions.

![Successful export sample](docs/screenshots/export-success.png)

### Dashboard capabilities

Product diagram of authentication, scope selection, reporting, results, and exports.

![Dashboard overview](docs/screenshots/dashboard-overview.svg)

### AI token tracking

Representative result layout for Azure AI usage evidence.

![AI token results](docs/screenshots/ai-token-results.svg)

### Export and deployment

Product diagram of the supported report formats and deployment paths.

![Exports and deployment](docs/screenshots/exports-and-deploy.svg)

### Reporting scope test gallery

These browser captures validate the graph composition for every reporting scope. They use fixed synthetic fixtures and are stamped **DOCUMENTATION TEST FIXTURE - NOT LIVE AZURE DATA**; they demonstrate layout and aggregation behavior only, not tenant findings.

<details>
<summary>Cost, allocation, and capacity scopes</summary>

| Tenant Spend Summary | Cost Summary |
| --- | --- |
| ![Tenant Spend Summary test fixture](docs/screenshots/report-scopes/tenant_spend_summary.jpg) | ![Cost Summary test fixture](docs/screenshots/report-scopes/cost_summary.jpg) |
| **Spend Visibility** | **Budget Forecasting** |
| ![Spend Visibility test fixture](docs/screenshots/report-scopes/spend_visibility.jpg) | ![Budget Forecasting test fixture](docs/screenshots/report-scopes/budget_forecasting.jpg) |
| **Storage Costs** | **Resource Group Costs** |
| ![Storage Costs test fixture](docs/screenshots/report-scopes/storage_costs.jpg) | ![Resource Group Costs test fixture](docs/screenshots/report-scopes/resource_group_costs.jpg) |
| **Subscription Cost Summary** | **Chargeback Showback** |
| ![Subscription Cost Summary test fixture](docs/screenshots/report-scopes/subscription_cost_summary.jpg) | ![Chargeback Showback test fixture](docs/screenshots/report-scopes/chargeback_showback.jpg) |
| **Quota Summary** | |
| ![Quota Summary test fixture](docs/screenshots/report-scopes/quota_summary.jpg) | |

</details>

<details>
<summary>Commitment and optimization scopes</summary>

| Reservation Savings | Expiring Reservations |
| --- | --- |
| ![Reservation Savings test fixture](docs/screenshots/report-scopes/reservation_savings.jpg) | ![Expiring Reservations test fixture](docs/screenshots/report-scopes/expiring_reservations.jpg) |
| **Reservations** | **Savings Plans** |
| ![Reservations test fixture](docs/screenshots/report-scopes/reservations.jpg) | ![Savings Plans test fixture](docs/screenshots/report-scopes/savings_plans.jpg) |
| **Optimization** | **Savings Potential** |
| ![Optimization test fixture](docs/screenshots/report-scopes/optimization.jpg) | ![Savings Potential test fixture](docs/screenshots/report-scopes/savings_potential.jpg) |
| **Reservations Potential** | **Architecture Efficiency** |
| ![Reservations Potential test fixture](docs/screenshots/report-scopes/reservations_potential.jpg) | ![Architecture Efficiency test fixture](docs/screenshots/report-scopes/architecture_efficiency.jpg) |
| **Idle Waste Detection** | |
| ![Idle Waste Detection test fixture](docs/screenshots/report-scopes/idle_waste_detection.jpg) | |

</details>

<details>
<summary>Governance and inventory scopes</summary>

| Anomaly Detection | Governance |
| --- | --- |
| ![Anomaly Detection test fixture](docs/screenshots/report-scopes/anomaly_detection.jpg) | ![Governance test fixture](docs/screenshots/report-scopes/governance.jpg) |
| **Tag Compliance** | **Sustainability** |
| ![Tag Compliance test fixture](docs/screenshots/report-scopes/tag_compliance.jpg) | ![Sustainability test fixture](docs/screenshots/report-scopes/sustainability.jpg) |

</details>

<details>
<summary>AI scopes and mobile layout</summary>

| AI FinOps | AI Token Tracking |
| --- | --- |
| ![AI FinOps test fixture](docs/screenshots/report-scopes/ai_finops.jpg) | ![AI Token Tracking test fixture](docs/screenshots/report-scopes/ai_token_tracking.jpg) |
| **Mobile graph layout** | |
| ![Mobile Idle Waste Detection test fixture](docs/screenshots/report-scopes/mobile-idle-waste-detection.jpg) | |

</details>

## Architecture

```mermaid
flowchart LR
   User[Signed-in user] --> UI[FastAPI dashboard]
   User --> Copilot[Microsoft 365 Copilot]
   Copilot --> Plugin[Declarative agent API plugin]
   Plugin --> API[Bounded FinOps API]
   UI --> API
   API --> ARM[Azure Resource Manager]
   API --> Cost[Cost Management]
   API --> Graph[Azure Resource Graph]
   API --> Advisor[Azure Advisor and Policy]
   API --> Monitor[Azure Monitor and usage APIs]
   ARM --> Report[Normalized report and source audit]
   Cost --> Report
   Graph --> Report
   Advisor --> Report
   Monitor --> Report
   Report --> Export[CSV, PDF, PPTX, SQLite]
```

Microsoft 365 Copilot hosts the language model. The API plugin forwards a delegated Azure token to the FastAPI backend. The backend does not use application-wide Azure permissions and cannot access resources beyond the signed-in user's RBAC scope.

## Key Features

1. Live-only reporting pipeline (no mock data).
2. Tenant and subscription discovery after sign-in.
3. 24 FinOps reporting domains, including AI token tracking and refreshable EA-style cost, reservation, quota, storage, resource-group, and subscription summaries.
4. Data enrichment for opaque IDs and quality scoring.
5. Export support for CSV, PDF, PPTX, and SQLite.
6. Strict live validation mode for trust gating.
7. Clear authentication context switching and CLI reauth support.
8. Publishable Microsoft 365 Copilot declarative agent package with delegated Azure RBAC.

## Refreshable EA-Style Reports

The report catalog includes live equivalents of the layouts in `SAMPLE PowerBi on Azure EA accounts.pptx`. The deck is a visual and reporting-taxonomy reference only; its values are never loaded by the application.

| Report | Authoritative live source |
| --- | --- |
| Tenant Spend Summary | Azure Cost Management actual cost, aggregated by usage date across selected subscriptions |
| Cost Summary | Azure Cost Management actual cost and usage detail |
| Reservation Savings | Azure Advisor reservation and commitment recommendations |
| Quota Summary | Azure Resource Graph region discovery and Azure Compute regional usage limits |
| Expiring Reservations | Azure Capacity reservation orders and reservations |
| Storage Costs | Azure Cost Management rows identified as storage services or meter categories |
| Resource Group Costs | Azure Cost Management actual cost aggregated by resource group and usage date |
| Subscription Cost Summary | Azure Cost Management actual cost aggregated by subscription, service, meter category, and usage date |

Select a tenant, one or more subscriptions, an optional date range, and a report domain, then choose **Run Live Report**. Running the report again refreshes it from Microsoft APIs using the current bearer token. PDF, PowerPoint, CSV, and SQLite exports are generated from that completed run and include collection time, scope, warnings, and source audit records.

The browser, PDF, and PowerPoint outputs render a distinct diagram composition for each domain, modeled on the corresponding sample page:

| Report | Diagrams and calculations |
| --- | --- |
| Tenant Spend Summary | One monthly actual-cost column series per selected subscription |
| Cost Summary | Subscription cost columns and share donut, monthly charge-type mix, and meter-category ranking |
| Reservation Savings | Incurred reservation cost over time and by reservation from Cost Management, plus Advisor savings by recommendation and impact |
| Quota Summary | Current usage by region, utilization ranking, and counters that reached or exceeded their limits |
| Expiring Reservations | Expiry cohorts, nearest expirations, matched incurred cost, and reserved-resource-type share |
| Storage Costs | Paired cost and usage-quantity shares and resource rankings |
| Resource Group Costs | Resource-group cost ranking, monthly cost columns, and cost share |
| Subscription Cost Summary | Monthly 100% subscription mix, subscription share, meter-category ranking, and resource ranking |

Each dashboard states its authenticated scope and exact aggregation logic. The detailed evidence tables remain below the diagrams for traceability.

Results reflect the signed-in user's Azure RBAC. Cost reports commonly require Cost Management Reader; reservation inventory requires permission to read `Microsoft.Capacity/reservationOrders` and reservations; quota reports require Resource Graph read access and `Microsoft.Compute/locations/usages/read`. A denied source is reported as a warning and never replaced with sample or fabricated rows.

## Microsoft 365 Copilot Agent

The `m365-agent` folder converts the live reporting API into a read-only declarative agent for Microsoft 365 Copilot. It includes the v1.8 agent manifest, v2.4 API plugin, constrained OpenAPI contract, OAuth packaging inputs, and a PowerShell package builder.

See [m365-agent/README.md](m365-agent/README.md) for tenant prerequisites, authentication setup, package creation, validation, and publishing steps.

The agent API is deployed to Azure Container Apps at:

`https://finops-ccoe-agent.whiteforest-caf556e3.westus.azurecontainerapps.io`

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
6. `app/services/diagrams.py`: canonical scope, logic, panel, and aggregation contracts for sample-matched report diagrams.
7. `app/services/exporters.py`: CSV/PDF/PPTX/SQLite export builders, including native vector diagram pages and slides.
8. `app/static/app.js`: frontend behavior and report execution flow.
9. `deploy-local.ps1`: one-command local run.
10. `desktop_launcher.py` and `FinOpsCCoE.spec`: Windows desktop application entry point and package definition.
11. `build-windows.ps1` and `installer/FinOpsCCoE.iss`: reproducible Windows application and installer build.
12. `deploy-function.ps1`: Linux Flex Consumption Function App deployment and verification.
13. `deploy-azure.ps1`: legacy App Service provisioning + source deployment.
14. `Dockerfile`: Python 3.11 image for Azure Container Apps.
15. `infra/azuredeploy.json`: ARM template for the App Service Deploy-to-Azure button.

## Download for Windows

[![Download Windows x64 installer (AMD and Intel)](https://img.shields.io/badge/Download-Windows_x64_AMD_%26_Intel-0078d4?logo=windows&logoColor=white)](https://github.com/jwgmpi-wolff/finops-ccoe-live-reporting/releases/latest/download/FinOpsCCoE-Setup.exe)
[![Download portable app](https://img.shields.io/badge/Download-Portable_ZIP-4c8bf5?logo=windows&logoColor=white)](https://github.com/jwgmpi-wolff/finops-ccoe-live-reporting/releases/latest/download/FinOpsCCoE-portable.zip)

The [latest GitHub release](https://github.com/jwgmpi-wolff/finops-ccoe-live-reporting/releases/latest) provides two Windows x64 packages. This repository is private: sign into GitHub with an account that has repository access before downloading; otherwise GitHub returns 404.

**AMD and Intel compatibility:** The same x64 installer and portable package run on both AMD64 and Intel 64 (x86-64) Windows PCs. No separate CPU-vendor download is required. These are not 32-bit x86 or native ARM64 builds.

The installer is also available from the [jerrywolff_microsoft repository release](https://github.com/jerrywolff_microsoft/finops-ccoe-live-reporting/releases/latest/download/FinOpsCCoE-Setup.exe). Use the repository your GitHub account can access.

| Package | Use |
| --- | --- |
| `FinOpsCCoE-Setup.exe` | Recommended per-user installer with Start menu and optional desktop shortcuts. No administrator access or Python installation is required. |
| `FinOpsCCoE-portable.zip` | Portable application folder. Extract the complete ZIP, then run `FinOpsCCoE.exe`; do not move the EXE away from its bundled files. |

Download `SHA256SUMS.txt` from the same release to verify either package:

```powershell
$expected = (Select-String -Path ".\SHA256SUMS.txt" -Pattern "FinOpsCCoE-Setup.exe").Line.Split()[0]
$actual = (Get-FileHash ".\FinOpsCCoE-Setup.exe" -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "Installer checksum does not match." }
```

The current packages are not digitally code-signed. Windows SmartScreen may therefore request confirmation; verify the SHA-256 checksum before selecting **Run anyway**. Live reports still require the signed-in user to have Azure CLI or browser OAuth authentication and Azure RBAC access.

Version 1.2.3 makes browser sign-in the default so Sign In opens Microsoft account authentication and the organization's MFA prompts. It also fixes sign-in failing before authentication on a fresh Azure CLI profile: normal sign-in no longer forces a global CLI logout, and an explicit session reset accepts an already-signed-out account. Version 1.2.2 added organization-neutral device-code sign-in for external organizations and non-domain PCs, an optional tenant ID/domain selector, browser fallback, a ten-minute sign-in window, and visible Azure CLI/Entra errors. See [cross-organization sign-in](#sign-in-from-another-organization-or-a-non-domain-pc) for prerequisites and policy requirements.

Version 1.2.1 preserves report results when an all-subscription selection includes subscriptions the authenticated user cannot query, and retries transient Cost Management throttling. Scope discovery remains best-effort and returns access warnings without blocking the report; only data from successfully queried subscriptions is shown. Version 1.2.0 adds universal chart interactivity: all graphs created for each report scope are now clickable to open a detail dive report with meter-level cost and usage breakdowns. Clickable charts span all 8 report domains (tenant_spend_summary, cost_summary, reservation_savings, quota_summary, expiring_reservations, storage_costs, resource_group_costs, subscription_cost_summary) and all 7 chart types (vertical columns, ranked bars, donuts, share bars, line charts, and data tables). Click any chart element to drill down by dimension (subscription, region, resource, meter category, etc.), view the filtered meter breakdown, and use the back button to navigate through multiple levels. Version 1.1.3 added clickable tenant-spend bars with meter-level live cost drilldowns. Cost tables now prioritize descriptive meter category, subcategory, meter, unit, service, cost, and usage columns. Version 1.1.2 added distinct sample-matched diagram compositions to the browser, PDF, and PowerPoint outputs and separated incurred reservation cost, potential savings, and expiry evidence. Exported values remain calculated only from the current live report run.

## Install on Windows

The Windows installer is the simplest desktop deployment. It installs per user, requires no administrator rights, adds Start menu and optional desktop shortcuts, and does not require Python on the destination computer.

To install a downloaded release interactively:

```powershell
Start-Process ".\FinOpsCCoE-Setup.exe"
```

To deploy it silently for the current Windows user:

```powershell
Start-Process ".\FinOpsCCoE-Setup.exe" -ArgumentList "/VERYSILENT", "/NORESTART" -Wait
```

The installer deploys to `%LOCALAPPDATA%\Programs\FinOpsCCoE` and can be removed from **Settings > Apps > Installed apps**.

During an install or upgrade, Setup automatically closes any running `FinOpsCCoE.exe` process before replacing application files. Open report tabs stop responding after the old process closes; launch the application again after Setup completes. This avoids access-denied prompts for locked bundled files such as `python311.dll`.

### Build the Windows packages

Build and install it from PowerShell in the repository root:

```powershell
.\build-windows.ps1
Start-Process ".\dist\installer\FinOpsCCoE-Setup.exe"
```

Launch **FinOps CCoE Live Reporting** from the Start menu after Setup completes. The application reserves an available loopback port selected by Windows, starts one local service on `127.0.0.1`, and opens the resulting report URL in the default browser. Launching the application again reopens the existing report instead of starting another server or authentication flow.

Prerequisites for live Azure data:

1. [Azure CLI installed](https://learn.microsoft.com/cli/azure/install-azure-cli-windows), or `FINOPS_ENTRA_CLIENT_ID` configured for direct browser OAuth. The Windows installer bundles the reporting app, not Azure CLI.
2. Azure RBAC access to the tenants and subscriptions being reported. The application does not elevate the signed-in user.

### Sign in from another organization or a non-domain PC

The desktop app does not require a Microsoft corporate account, Microsoft-domain computer, or domain join. Use your own organization's Microsoft Entra account with Azure RBAC access to the subscriptions you want to report.

1. Install Azure CLI if it is not already installed, then restart the reporting app so it can detect the CLI.
2. Optionally enter your organization's tenant ID or domain, such as `contoso.onmicrosoft.com`. Leaving it blank uses Azure CLI's organization-neutral account selection, with no tenant pinned.
3. Leave **Browser (opens Microsoft sign-in and organization MFA)** selected and click **Sign In with Entra**.
4. Complete Microsoft account selection, password, and any MFA prompts in the browser that opens.
5. Keep the report page open. The app waits up to ten minutes, displays login failures rather than hiding them, and loads your Azure context after the CLI reports success.

Normal sign-in does not require an existing CLI account and does not log out other Azure CLI sessions first. Microsoft handles the password, Authenticator, security-key, and other MFA challenges on its sign-in page according to your organization's policies. The app cannot force a new MFA challenge when Microsoft considers an existing session sufficient.

If the browser does not open or its localhost callback fails, select **Device code fallback (no localhost callback)** instead. Open the Microsoft device sign-in link displayed in the app, enter the displayed code, and choose your organization's account. Only enter codes you requested yourself. Issuing a code alone does not trigger an MFA prompt; you must open the link and enter the code. Organizations may block this fallback through Conditional Access.

Browser mode uses a temporary localhost callback; do not bookmark or reopen an old callback tab. Azure CLI runs without a terminal, with its Windows broker and terminal subscription selector disabled. Only one sign-in can be active at a time.

Your organization's Conditional Access, admin consent, device-compliance, and Azure RBAC policies still apply. The app does not bypass those policies. If sign-in is rejected, the app displays the Azure CLI/Entra error for your administrator to investigate. Azure Resource Manager access is required even when the account can sign into Microsoft 365.

Administrators who do not want to install Azure CLI can configure browser OAuth with their own Entra app registration. For sharing across organizations, register the app for **Accounts in any organizational directory**, grant delegated Azure Service Management `user_impersonation`, obtain any required tenant admin consent, and keep `FINOPS_ENTRA_AUTHORITY=https://login.microsoftonline.com/organizations`. A single-tenant registration only accepts accounts allowed by that tenant. Configure `FINOPS_ENTRA_REDIRECT_URI` to an exact registered SPA redirect URL; the desktop app selects a dynamic port, so a fixed local web deployment is needed for this browser-only configuration.

Generated export staging files are written to `%LOCALAPPDATA%\FinOpsCCoE\exports`. When an export button is selected, Microsoft Edge prompts for the final destination and filename; browsers without the native save picker use their configured download behavior.

For a silent per-user installation:

```powershell
Start-Process ".\dist\installer\FinOpsCCoE-Setup.exe" -ArgumentList "/VERYSILENT", "/NORESTART" -Wait
```

The script creates an isolated `.build-venv`, runs the tests, builds the Application Control-compatible application folder at `dist\FinOpsCCoE`, and packages it as `dist\installer\FinOpsCCoE-Setup.exe`. Inno Setup 6 is installed with `winget` when it is not already available. Use `-SkipInstaller` to build only the application folder.

Generated application and installer files under `dist` are intentionally excluded from Git. Rebuild them from `build-windows.ps1` for each release so the package matches the committed source.

When GitHub-hosted runners are enabled, maintainers publish both packages by pushing a version tag. The `Publish Windows release` workflow runs tests, rebuilds from source, creates checksums, and attaches the files to the matching GitHub release:

```powershell
git tag v1.1.3
git push jwgmpi-wolff v1.1.3
```

If enterprise policy disables GitHub-hosted runners, build locally and publish the same assets with GitHub CLI authentication for the repository owner:

```powershell
.\build-windows.ps1
Compress-Archive -Path ".\dist\FinOpsCCoE\*" -DestinationPath ".\dist\FinOpsCCoE-portable.zip" -Force
$assets = @(".\dist\installer\FinOpsCCoE-Setup.exe", ".\dist\FinOpsCCoE-portable.zip")
$lines = foreach ($asset in $assets) {
   $hash = (Get-FileHash -Algorithm SHA256 $asset).Hash.ToLowerInvariant()
   "$hash  $([System.IO.Path]::GetFileName($asset))"
}
$lines | Set-Content ".\dist\SHA256SUMS.txt" -Encoding ascii
gh release create v1.1.3 @assets ".\dist\SHA256SUMS.txt" --repo jwgmpi-wolff/finops-ccoe-live-reporting --generate-notes
```

To verify the unpackaged application before installing:

```powershell
.\dist\FinOpsCCoE\FinOpsCCoE.exe
```

The browser address will contain a dynamically selected port, for example `http://127.0.0.1:49685/api/run_finops_report`. Confirm that the report loads; the exact port will differ on each launch.

## Prerequisites

- Python 3.11 or newer
- PowerShell 7 or Windows PowerShell 5.1
- Azure CLI for local CLI authentication and Azure deployment
- An Azure account with access to at least one subscription
- Microsoft 365 Agents Toolkit when validating or publishing the Copilot agent
- Microsoft 365 Copilot and custom app upload enabled in the publishing tenant

## Run Locally

From PowerShell in the repository root:

```powershell
git clone https://github.com/jerrywolff_microsoft/finops-ccoe-live-reporting.git
Set-Location finops-ccoe-live-reporting
.\deploy-local.ps1
```

The script creates `.venv`, upgrades pip, installs `requirements.txt`, reports whether browser Entra authentication is configured, and starts Uvicorn at `http://127.0.0.1:8010`.

To select another interface or port:

```powershell
.\deploy-local.ps1 -HostName 0.0.0.0 -Port 8080
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

The script validates the active tenant and subscription, runs the tests, creates or reuses a Linux Python 3.11 Flex Consumption Function App and deployment storage, publishes with a remote build, and verifies HTTPS health. For an existing app, it resolves the configured `AzureWebJobsStorage` account and enables public network access for Azure Functions platform artifact deployment; the storage account continues to block anonymous blob access.

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

Authenticate to the intended tenant and subscription first:

```powershell
az login
az account set --subscription '<subscription-id-or-name>'
```

Then provision and upload the application:

```powershell
./deploy-azure.ps1 `
   -ResourceGroup rg-finops-live `
   -Location eastus `
   -AppName finops-live-reporting-demo `
   -EntraClientId <tenant-owned-entra-client-id> `
   -EntraAuthority https://login.microsoftonline.com/<tenant-id>
```

Use `-Sku` to select another App Service plan SKU when needed:

```powershell
./deploy-azure.ps1 -ResourceGroup rg-finops-live -Location eastus -AppName finops-live-reporting-demo -Sku F1
```

What the script does:

1. Validates Azure CLI login.
2. Creates/updates resource group.
3. Creates Linux App Service plan.
4. Creates/updates Python web app.
5. Configures startup command and app settings.
6. Performs zip deployment of the project.

The app name must be globally unique. The signed-in account must be able to create a resource group, App Service plan, and web app. If App Service reports a zero VM quota, use the Container Apps Consumption path below or request App Service quota.

## Deploy to Azure Container Apps

Container Apps Consumption is the fallback when the subscription has no App Service VM quota. The deployed tenant uses the existing `wolffacr` registry and the `finops-ccoe-env` Consumption environment in West US.

```powershell
az acr build --registry wolffacr --image finops-ccoe-agent:20260729 .

az containerapp create `
   --name finops-ccoe-agent `
   --resource-group rg-finops-ccoe-agent `
   --environment finops-ccoe-env `
   --image wolffacr.azurecr.io/finops-ccoe-agent:20260729 `
   --target-port 8000 `
   --ingress external `
   --min-replicas 0 `
   --max-replicas 2 `
   --cpu 0.5 `
   --memory 1Gi
```

Prefer managed identity with the `AcrPull` role for private registry access. If the deploying account cannot create role assignments, a registry credential can be stored as a Container Apps secret instead; never print or commit that credential.

## Build the Microsoft 365 Copilot Agent

After deploying the HTTPS API, create the OAuth authentication configuration described in [m365-agent/README.md](m365-agent/README.md), then build the package:

```powershell
.\m365-agent\build-package.ps1 `
   -ApiBaseUrl 'https://<your-api-host>' `
   -OAuthReferenceId '<oauth-vault-reference-id>' `
   -TenantIdOrDomain '<tenant-id>' `
   -ContactEmail '<support-email>'
```

The generated `m365-agent/dist/finops-ccoe-agent.zip` contains the Teams app manifest, declarative agent manifest, API plugin, OpenAPI document, and icons. The `dist` folder is ignored by Git because it contains tenant-specific package values.

Validate and sideload the package with Microsoft 365 Agents Toolkit before submitting it to the organizational app catalog.

## Environment Configuration

| Variable | Required | Purpose |
| --- | --- | --- |
| `FINOPS_ENTRA_CLIENT_ID` | No | Enables the browser Microsoft Entra sign-in path. |
| `FINOPS_ENTRA_AUTHORITY` | No | Overrides the Entra authority URL. |
| `FINOPS_ENTRA_REDIRECT_URI` | No | Overrides the browser redirect URI; `deploy-azure.ps1` sets it to the App Service URL. |

When `FINOPS_ENTRA_CLIENT_ID` is not set, local Azure CLI session authentication remains available. The hosted Copilot API routes receive delegated bearer tokens from the API plugin and do not rely on Azure CLI.

Register the deployed App Service URL as a Single-page application redirect URI on the tenant-owned Entra application.

## Deploy Live Reporting and Copilot

In VS Code GitHub Copilot Chat, run `/deploy-finops-copilot` for a one-request workflow that deploys this live-reporting app and its Microsoft 365 Copilot agent package from `m365-agent`.

See [One-Request Copilot Deployment](docs/COPILOT_ONE_REQUEST_DEPLOYMENT.md).

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest -q
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
4. Include Dockerfile and .dockerignore for Azure Container Apps Consumption deployment.
5. Include screenshots under docs/screenshots and reference only project-related images in README.
6. Include tests and clear onboarding instructions.

Microsoft 365 Copilot agent requirements:
1. Add m365-agent/appPackage/declarativeAgent.json using the current Microsoft declarative agent schema.
2. Add m365-agent/appPackage/manifest.template.json using the current Microsoft 365 app manifest schema.
3. Add m365-agent/appPackage/finops-api-plugin.template.json using an OpenAPI runtime and OAuthPluginVault delegated authentication.
4. Add m365-agent/appPackage/finops-openapi.template.yaml with listTenants, listSubscriptions, and runFinOpsReport operations.
5. Add m365-agent/build-package.ps1 that expands API URL, host, tenant, app ID, contact email, and OAuth reference placeholders; generates valid color and outline PNG icons; validates generated JSON; and creates a six-file ZIP package.
6. Make the package builder compatible with Windows PowerShell 5.1 and PowerShell 7, including UTF-8 without BOM output.
7. Add bounded request and response models for Copilot. Limit report rows to a configurable maximum of 100 and return total count, returned count, and truncation state.
8. Add privacy and terms routes and reference them from the app and plugin manifests.
9. Keep all actions read-only, mark them non-consequential, and instruct the model to preserve timestamps, warnings, data quality, and source evidence.
10. Never commit OAuth references, client secrets, generated package files, access tokens, or tenant environment files.

Required project structure:
- app/main.py, app/config.py, app/models.py
- app/services/azure_live.py, reporting.py, enrichment.py, exporters.py
- app/templates/index.html and app/static/app.js, styles.css
- tests/test_api.py
- deploy-local.ps1 and deploy-azure.ps1
- Dockerfile and .dockerignore
- infra/azuredeploy.json
- m365-agent/README.md, build-package.ps1, and appPackage templates
- docs/screenshots with only dashboard, result, export, and deployment visuals
- requirements.txt, .gitignore, and README.md

Documentation requirements:
1. Write a complete README with prerequisites, architecture, local deployment, Azure deployment, Container Apps fallback, agent packaging, testing, troubleshooting, screenshots, and this full regeneration prompt.
2. Add a Deploy to Azure badge linked to infra/azuredeploy.json.
3. Add a Run Locally badge linked to the local instructions.
4. State clearly that ARM must be able to access the template URL and provide deploy-azure.ps1 as the authenticated private-repository path.
5. Do not claim that conceptual SVG diagrams are live screenshots; label each visual accurately.

Strict validation gate:
- Fail report execution if live source connectivity is unavailable and strict-live mode is enabled.
- Display explicit error instead of stale fallback.
- Reject output if more than 5 percent of key business fields are unresolved after enrichment.

Implementation quality gate:
1. Use typed Pydantic request and response models.
2. Keep API calls asynchronous with explicit timeouts and actionable errors.
3. Escape user-controlled values in the browser UI and render structured tables without unsafe HTML.
4. Keep generated files, virtual environments, caches, exports, credentials, and secrets out of Git.
5. Test unauthenticated rejection, bounded agent responses, report domains, live-source adapters with monkeypatching, export behavior, and auth-context cleanup.
6. Run the complete test suite, parse all JSON manifests, validate the OpenAPI document, build and inspect the agent ZIP, and verify all relative README links.

Now implement the entire project end-to-end. Create every listed file with complete working content, wire all routes and deployment paths, run validation, fix failures, and finish with exact local, Azure, Container Apps, and Microsoft 365 publication commands. Do not stop at a scaffold or use mock runtime report data.
```

## License

This project is provided as-is for internal enablement and engineering acceleration.
