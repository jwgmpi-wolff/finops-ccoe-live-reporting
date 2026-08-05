param(
  [Parameter(Mandatory = $true)] [string]$SubscriptionId,
  [Parameter(Mandatory = $true)] [string]$ResourceGroup,
  [Parameter(Mandatory = $true)] [string]$Location,
  [Parameter(Mandatory = $true)] [ValidatePattern("^[a-zA-Z0-9-]{2,60}$")] [string]$FunctionAppName,
  [string]$TenantId = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

function Invoke-External {
  param(
    [Parameter(Mandatory = $true)] [string]$FilePath,
    [Parameter(Mandatory = $true)] [string[]]$Arguments
  )
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: $FilePath"
  }
}

foreach ($commandName in @("az", "func")) {
  if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
    throw "Required command is not installed or not on PATH: $commandName"
  }
}

Write-Host "[1/7] Validating Azure identity and target context..."
$account = az account show --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
  throw "Azure CLI is not signed in. Run 'az login' and retry."
}
if ($TenantId -and $account.tenantId -ne $TenantId) {
  throw "The active Azure CLI tenant does not match -TenantId. Sign in to the intended tenant and retry."
}
Invoke-External -FilePath "az" -Arguments @("account", "set", "--subscription", $SubscriptionId)
$activeSubscription = az account show --query id --output tsv
if ($LASTEXITCODE -ne 0 -or $activeSubscription -ne $SubscriptionId) {
  throw "Azure CLI could not select the requested subscription."
}

Write-Host "[2/7] Running application tests..."
$python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
Invoke-External -FilePath $python -Arguments @("-m", "pytest", "-q")

Write-Host "[3/7] Creating or updating the resource group..."
Invoke-External -FilePath "az" -Arguments @("group", "create", "--name", $ResourceGroup, "--location", $Location, "--output", "none")

$storageSeed = ($FunctionAppName.ToLowerInvariant() -replace "[^a-z0-9]", "")
$hashBytes = [System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes("$SubscriptionId/$ResourceGroup/$FunctionAppName"))
$hash = [Convert]::ToHexString($hashBytes).Substring(0, 6).ToLowerInvariant()
$storageName = ($storageSeed.Substring(0, [Math]::Min(17, $storageSeed.Length)) + $hash).PadRight(3, "0")

Write-Host "[4/7] Creating deployment storage if needed..."
Invoke-External -FilePath "az" -Arguments @(
  "storage", "account", "create", "--name", $storageName,
  "--resource-group", $ResourceGroup, "--location", $Location,
  "--sku", "Standard_LRS", "--allow-blob-public-access", "false", "--output", "none"
)

$existingApp = az functionapp show --name $FunctionAppName --resource-group $ResourceGroup --query name --output tsv 2>$null
if (-not $existingApp) {
  Write-Host "[5/7] Creating Linux Flex Consumption Function App..."
  Invoke-External -FilePath "az" -Arguments @(
    "functionapp", "create", "--name", $FunctionAppName,
    "--resource-group", $ResourceGroup, "--storage-account", $storageName,
    "--flexconsumption-location", $Location, "--runtime", "python",
    "--runtime-version", "3.11", "--functions-version", "4", "--output", "none"
  )
} else {
  Write-Host "[5/7] Function App already exists; preserving its resource configuration."
}

Invoke-External -FilePath "az" -Arguments @(
  "functionapp", "config", "appsettings", "set", "--name", $FunctionAppName,
  "--resource-group", $ResourceGroup, "--settings", "FINOPS_APP_VERSION=1.0.4", "--output", "none"
)

Write-Host "[6/7] Publishing application code with a remote build..."
Invoke-External -FilePath "func" -Arguments @("azure", "functionapp", "publish", $FunctionAppName, "--python", "--build", "remote")

Write-Host "[7/7] Verifying the live health endpoint..."
$healthUrl = "https://$FunctionAppName.azurewebsites.net/api/health"
$health = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 60
if ($health.status -ne "ok") {
  throw "Deployment completed, but the health endpoint did not return status 'ok'."
}

Write-Host "Deployment verified: https://$FunctionAppName.azurewebsites.net/api/run_finops_report" -ForegroundColor Green