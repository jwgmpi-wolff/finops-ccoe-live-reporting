# Copyright (c) 2026 jerry wolff

param(
  [Parameter(Mandatory = $true)] [string]$ResourceGroup,
  [Parameter(Mandatory = $true)] [string]$Location,
  [Parameter(Mandatory = $true)] [string]$AppName,
  [string]$PlanName = "finops-asp-linux",
  [string]$Sku = "B1",
  [string]$Runtime = "PYTHON:3.11",
  [string]$EntraClientId,
  [string]$EntraAuthority = "https://login.microsoftonline.com/organizations",
  [switch]$SkipZipDeploy
)

$ErrorActionPreference = "Stop"

function Invoke-Az {
  param([string[]]$CommandArgs)
  & az @CommandArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Azure CLI command failed: az $($CommandArgs -join ' ')"
  }
}

Write-Host "[1/6] Ensuring Azure CLI login..."
Invoke-Az -CommandArgs @("account", "show", "-o", "none")

Write-Host "[2/6] Creating resource group if needed..."
Invoke-Az -CommandArgs @("group", "create", "--name", $ResourceGroup, "--location", $Location, "-o", "none")

Write-Host "[3/6] Creating Linux App Service plan if needed (SKU: $Sku)..."
Invoke-Az -CommandArgs @(
  "appservice", "plan", "create",
  "--name", $PlanName,
  "--resource-group", $ResourceGroup,
  "--is-linux",
  "--sku", $Sku,
  "-o", "none"
)

Write-Host "[4/6] Creating/updating Web App..."
Invoke-Az -CommandArgs @(
  "webapp", "create",
  "--name", $AppName,
  "--resource-group", $ResourceGroup,
  "--plan", $PlanName,
  "--runtime", $Runtime,
  "-o", "none"
)

Write-Host "[5/6] Applying runtime settings..."
$appSettings = @(
  "SCM_DO_BUILD_DURING_DEPLOYMENT=true",
  "WEBSITES_PORT=8000",
  "FINOPS_APP_VERSION=1.0.4",
  "FINOPS_ENTRA_AUTHORITY=$EntraAuthority",
  "FINOPS_ENTRA_REDIRECT_URI=https://$AppName.azurewebsites.net"
)
if ($EntraClientId) {
  $appSettings += "FINOPS_ENTRA_CLIENT_ID=$EntraClientId"
}

Invoke-Az -CommandArgs @(
  "webapp", "config", "appsettings", "set",
  "--name", $AppName,
  "--resource-group", $ResourceGroup,
  "--settings",
  $appSettings,
  "-o", "none"
)

Invoke-Az -CommandArgs @(
  "webapp", "config", "set",
  "--name", $AppName,
  "--resource-group", $ResourceGroup,
  "--startup-file", "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000",
  "-o", "none"
)

if (-not $SkipZipDeploy) {
  Write-Host "[6/6] Deploying source via zip deployment..."
  $zipPath = Join-Path $PWD "app-deploy.zip"
  if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
  }

  Compress-Archive -Path @(
    "app",
    "tests",
    "requirements.txt",
    "README.md"
  ) -DestinationPath $zipPath -Force

  Invoke-Az -CommandArgs @(
    "webapp", "deployment", "source", "config-zip",
    "--resource-group", $ResourceGroup,
    "--name", $AppName,
    "--src", $zipPath,
    "-o", "none"
  )

  Remove-Item $zipPath -Force
}

$hostName = az webapp show --name $AppName --resource-group $ResourceGroup --query defaultHostName -o tsv
Write-Host "Deployment complete: https://$hostName" -ForegroundColor Green
