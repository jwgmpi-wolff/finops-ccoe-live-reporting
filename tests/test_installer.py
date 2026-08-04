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