param(
  [switch]$SkipInstaller
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
    throw "Command failed: $FilePath $($Arguments -join ' ')"
  }
}

$buildPython = Join-Path $repoRoot ".build-venv\Scripts\python.exe"
if (-not (Test-Path $buildPython)) {
  Write-Host "[1/5] Creating isolated build environment..."
  Invoke-External -FilePath "python" -Arguments @("-m", "venv", ".build-venv")
} else {
  Write-Host "[1/5] Reusing isolated build environment..."
}

Write-Host "[2/5] Installing pinned runtime and packaging dependencies..."
Invoke-External -FilePath $buildPython -Arguments @("-m", "pip", "install", "--disable-pip-version-check", "-r", "requirements.txt", "-r", "requirements-build.txt")

Write-Host "[3/5] Running tests..."
Invoke-External -FilePath $buildPython -Arguments @("-m", "pytest", "-q")

Write-Host "[4/5] Building standalone Windows application..."
Invoke-External -FilePath $buildPython -Arguments @("-m", "PyInstaller", "--clean", "--noconfirm", "FinOpsCCoE.spec")
$appPath = Join-Path $repoRoot "dist\FinOpsCCoE"
$exePath = Join-Path $appPath "FinOpsCCoE.exe"
if (-not (Test-Path $exePath)) {
  throw "Expected executable was not created: $exePath"
}

if ($SkipInstaller) {
  Write-Host "Standalone application ready: $appPath" -ForegroundColor Green
  exit 0
}

Write-Host "[5/5] Building per-user Windows installer..."
$isccCandidates = @(
  (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
  (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
  (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
)
$iscc = $isccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) {
  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if (-not $winget) {
    throw "Inno Setup 6 is required to build the installer. Install it, or rerun with -SkipInstaller."
  }
  Invoke-External -FilePath $winget.Source -Arguments @(
    "install", "--id", "JRSoftware.InnoSetup", "--exact", "--silent",
    "--accept-package-agreements", "--accept-source-agreements"
  )
  $iscc = $isccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}
if (-not $iscc) {
  throw "Inno Setup installed but ISCC.exe could not be located. Rerun after opening a new terminal."
}

Invoke-External -FilePath $iscc -Arguments @("installer\FinOpsCCoE.iss")
$installerPath = Join-Path $repoRoot "dist\installer\FinOpsCCoE-Setup.exe"
if (-not (Test-Path $installerPath)) {
  throw "Expected installer was not created: $installerPath"
}

Write-Host "Windows installer ready: $installerPath" -ForegroundColor Green