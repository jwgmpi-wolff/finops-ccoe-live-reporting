from pathlib import Path


INSTALLER_SCRIPT = Path(__file__).parents[1] / "installer" / "FinOpsCCoE.iss"


def test_installer_stops_running_app_before_replacing_files():
    script = INSTALLER_SCRIPT.read_text(encoding="utf-8")

    assert "CloseApplications=yes" in script
    assert "CloseApplicationsFilter={#AppExeName}" in script
    assert "RestartApplications=no" in script
    assert "function PrepareToInstall" in script
    assert "taskkill.exe" in script
    assert "/F /T /IM {#AppExeName}" in script


def test_windows_build_bundles_verified_cli_for_installer_and_portable_app():
    script = (INSTALLER_SCRIPT.parents[1] / "build-windows.ps1").read_text(encoding="utf-8")

    assert 'Join-Path $appPath "azure-cli"' in script
    assert "Get-FileHash -Path $cliArchive -Algorithm SHA256" in script
    assert "ZipFile]::ExtractToDirectory($cliArchive, $cliPath)" in script
    assert script.index("ExtractToDirectory") < script.index("if ($SkipInstaller)")
    assert '$env:PATH = "$env:SystemRoot\\System32;$env:SystemRoot"' in script
    assert 'Invoke-External -FilePath $bundledCli -Arguments @("version", "--output", "json")' in script