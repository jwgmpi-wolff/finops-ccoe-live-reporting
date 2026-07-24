param(
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8010
)

$ErrorActionPreference = "Stop"

Write-Host "[1/4] Preparing virtual environment..."
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  python -m venv .venv
}

Write-Host "[2/4] Installing dependencies..."
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "[3/4] Validating configuration..."
if (-not $env:FINOPS_ENTRA_CLIENT_ID) {
  Write-Host "FINOPS_ENTRA_CLIENT_ID is not set. Browser OAuth stays disabled; Azure CLI auth remains available." -ForegroundColor Yellow
}

Write-Host "[4/4] Starting app on http://$HostName`:$Port ..."
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host $HostName --port $Port --reload
