# FinOps CCoE Deployment Plan

## Status
Validated

## Objective
Deliver and document three supported delivery paths from this repository:

1. Windows self-installer built from `build-windows.ps1` and `installer/FinOpsCCoE.iss`.
2. Local self-hosted launch using `deploy-local.ps1`.
3. Azure Functions Flex Consumption deployment using `deploy-function.ps1`.

## Current State

- The repository already contains Windows packaging, local launch, Azure Functions entry points, an Azure Function deployment script, and README deployment guidance.
- The application uses the caller's delegated Azure identity for live reports. Deployment must not introduce a broader identity or store credentials in source control.
- Current release version: `1.2.1`.

## Proposed Work

1. Review and validate each existing delivery script for Windows compatibility, parameter validation, idempotency, and clear failure messages.
2. Ensure the Windows installer and local launcher are discoverable from concise README quick-start instructions.
3. Confirm the Function App deployment script requires an explicit subscription, tenant, resource group, region, and globally unique app name; it will verify the active Azure CLI context before any Azure mutation.
4. Add or refine a single-command quick deploy wrapper only if the existing Function deployment script lacks an ergonomic parameterized entry point.
5. Run script parsing, Python tests, a Windows installer build, and pre-deployment validation.
6. After validation, deploy to the approved existing Function App and verify the HTTPS health endpoint.

## Security and Operations

- Use the signed-in Azure CLI principal and retain delegated user RBAC for report data.
- Do not print or commit access tokens, secrets, or customer data.
- Treat inaccessible subscriptions as partial coverage and surface warnings.
- Do not infer Azure tenant, subscription, or deployment region.

## Required Azure Context

- Subscription: `wolffentpSub` (`5755893a-8056-4ba8-9916-1133c80a80f3`)
- Tenant: `wolff` (`e594a530-1ec9-4192-a8d4-a9111f8cffa7`)
- Resource group: `rg-Finops`
- Region: `East US`
- Existing Function App: `func-Finops-y6xgk3`

## Validation Gates

- Python test suite passes.
- PowerShell scripts parse successfully.
- Windows installer builds successfully.
- Azure deployment validation succeeds before resource creation.
- Deployed HTTPS `/api/health` responds successfully.

### All validation checks pass

- [x] Confirm Azure CLI authentication, subscription, tenant, and approved Function App target.
- [x] Confirm Azure Functions Core Tools and Azure CLI are installed.
- [x] Run the full Python test suite.
- [x] Parse `deploy-function.ps1` with the PowerShell parser.
- [x] Confirm the target Function App is HTTPS-only and running before code deployment.
- [x] Static role review: no Bicep/Terraform role assignments or managed identities are defined by this deployment path; report access remains delegated to each caller's Azure identity.
- [x] Publish to the approved existing Function App with remote build.
- [x] Verify the deployed HTTPS health endpoint and Function App state.

## Role Assignment Verification

- Status: Verified
- Identities checked: None. The Function App does not use a managed identity to query Azure resources.
- Roles confirmed: Not applicable. Live report calls forward the caller's delegated bearer token and remain within that caller's RBAC boundary.
- Issues: None in the deployment infrastructure.

## Validation Proof

- 2026-08-29: Azure CLI context confirmed for the approved subscription and tenant.
- 2026-08-29: Existing Function App confirmed running in `rg-Finops`, East US, with HTTPS-only enabled.
- 2026-08-29: `./.venv/Scripts/python.exe -m pytest tests -q` completed successfully: 32 passed.
- 2026-08-29: PowerShell syntax validation completed successfully for `deploy-function.ps1`.
- 2026-08-29: `build-windows.ps1` rebuilt `dist/installer/FinOpsCCoE-Setup.exe` successfully (27.04 MB; SHA-256 `42ACC2715AFF21EEFBF7A5AE2E836EA9E9076C4123AB3901089D442A6303DEF6`).
- 2026-08-30: Remote ZipDeploy initially failed because `AzureWebJobsStorage` had public network access disabled. Public network access was approved and enabled for `stfinopsy6xgk3ym`; the subsequent remote build completed successfully.
- 2026-08-30: Production verification passed: `https://func-finops-y6xgk3.azurewebsites.net/api/health` returned `{"status":"ok","service":"FinOps CCoE Live Reporting","version":"1.2.1"}`.