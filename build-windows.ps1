# Copyright (c) 2026 jerry wolff

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
  Write-Host "[1/6] Creating isolated build environment..."
  Invoke-External -FilePath "python" -Arguments @("-m", "venv", ".build-venv")
} else {
  Write-Host "[1/6] Reusing isolated build environment..."
}

Write-Host "[2/6] Installing pinned runtime and packaging dependencies..."
Invoke-External -FilePath $buildPython -Arguments @("-m", "pip", "install", "--disable-pip-version-check", "-r", "requirements.txt", "-r", "requirements-build.txt")

Write-Host "[3/6] Running tests..."
Invoke-External -FilePath $buildPython -Arguments @("-m", "pytest", "-q")

Write-Host "[4/6] Building standalone Windows application..."
Invoke-External -FilePath $buildPython -Arguments @("-m", "PyInstaller", "--clean", "--noconfirm", "FinOpsCCoE.spec")
$appPath = Join-Path $repoRoot "dist\FinOpsCCoE"
$exePath = Join-Path $appPath "FinOpsCCoE.exe"
if (-not (Test-Path $exePath)) {
  throw "Expected executable was not created: $exePath"
}

Write-Host "[5/6] Bundling the official portable Azure CLI authentication runtime..."
$cliManifest = Get-Content -LiteralPath (Join-Path $repoRoot "windows-runtime.json") -Raw | ConvertFrom-Json
$cliVersion = $cliManifest.version
$cliSha256 = $cliManifest.sha256
$cliArchive = Join-Path $repoRoot "build\azure-cli-$cliVersion-x64.zip"
$cliDownloadUrl = $cliManifest.url
if (-not (Test-Path $cliArchive)) {
  Invoke-WebRequest -Uri $cliDownloadUrl -OutFile $cliArchive -UseBasicParsing
}
if ((Get-FileHash -Path $cliArchive -Algorithm SHA256).Hash -ne $cliSha256) {
  throw "The portable Azure CLI archive does not match the pinned SHA-256 checksum."
}
$cliPath = Join-Path $appPath "azure-cli"
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory($cliArchive, $cliPath)
$bundledCli = Join-Path $cliPath "bin\az.cmd"
if (-not (Test-Path $bundledCli)) {
  throw "The bundled Azure CLI launcher is missing: $bundledCli"
}
$originalPath = $env:PATH
$originalConfig = $env:AZURE_CONFIG_DIR
$originalExtensions = $env:AZURE_EXTENSION_DIR
try {
  $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
  $env:AZURE_CONFIG_DIR = Join-Path $repoRoot "build\azure-cli-smoke-profile"
  $env:AZURE_EXTENSION_DIR = Join-Path $env:AZURE_CONFIG_DIR "cliextensions"
  Invoke-External -FilePath $bundledCli -Arguments @("version", "--output", "json")
} finally {
  $env:PATH = $originalPath
  $env:AZURE_CONFIG_DIR = $originalConfig
  $env:AZURE_EXTENSION_DIR = $originalExtensions
}

if ($SkipInstaller) {
  Write-Host "Standalone application ready: $appPath" -ForegroundColor Green
  exit 0
}

Write-Host "[6/6] Building per-user Windows installer..."
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