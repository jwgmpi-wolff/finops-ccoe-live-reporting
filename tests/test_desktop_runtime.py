import hashlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import zipfile

import pytest

from app import desktop_runtime as runtime


def test_source_runs_do_not_install_components(monkeypatch):
    monkeypatch.setattr(runtime.sys, "frozen", False, raising=False)

    assert runtime.ensure_windows_runtime() is True


def test_runtime_verification_rejects_wrong_version(monkeypatch, tmp_path):
    launcher = tmp_path / "bin" / "az.cmd"
    launcher.parent.mkdir()
    launcher.touch()
    monkeypatch.setattr(
        runtime.subprocess, "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, '{"azure-cli":"0.0.0"}', ""),
    )

    with pytest.raises(ValueError, match="runtime version"):
        runtime._verify_runtime(tmp_path)


def test_runtime_verification_does_not_use_system_path(monkeypatch, tmp_path):
    launcher = tmp_path / "bin" / "az.cmd"
    launcher.parent.mkdir()
    launcher.touch()
    version, _, _ = runtime._manifest()
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, json.dumps({"azure-cli": version}), "")

    monkeypatch.setattr(runtime.subprocess, "run", fake_run)
    monkeypatch.setenv("PATH", "untrusted-system-cli")

    runtime._verify_runtime(tmp_path)

    assert captured["command"][0] == str(tmp_path / "python.exe")
    assert "untrusted-system-cli" not in captured["env"]["PATH"]
    assert captured["timeout"] == 30


@pytest.mark.parametrize("approve", [False, True])
def test_missing_runtime_requests_permission_before_repair(monkeypatch, tmp_path, approve):
    repaired = []
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime, "runtime_directory", lambda: tmp_path / "azure-cli")
    monkeypatch.setattr(runtime, "_verify_runtime", lambda _: (_ for _ in ()).throw(OSError("missing")))
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *args, **kwargs: approve)
    monkeypatch.setattr(runtime, "_repair_runtime", repaired.append)

    assert runtime.ensure_windows_runtime() is approve
    assert repaired == ([tmp_path / "azure-cli"] if approve else [])


def test_repair_error_is_shown_and_prevents_startup(monkeypatch, tmp_path):
    errors = []
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime, "runtime_directory", lambda: tmp_path / "azure-cli")
    monkeypatch.setattr(runtime, "_verify_runtime", lambda _: (_ for _ in ()).throw(OSError("missing")))
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        runtime, "_repair_runtime", lambda _: (_ for _ in ()).throw(ValueError("SHA-256 verification failed")),
    )
    monkeypatch.setattr("tkinter.messagebox.showerror", lambda title, message: errors.append(message))

    assert runtime.ensure_windows_runtime() is False
    assert "SHA-256 verification failed" in errors[0]


@pytest.mark.parametrize("valid_hash", [False, True])
def test_repair_verifies_download_before_replacing_existing_files(monkeypatch, tmp_path, valid_hash):
    contents = io.BytesIO()
    with zipfile.ZipFile(contents, "w") as package:
        package.writestr("bin/az.cmd", "launcher")
        package.writestr("python.exe", "runtime")
    archive = contents.getvalue()
    digest = hashlib.sha256(archive).hexdigest() if valid_hash else "0" * 64
    destination = tmp_path / "azure-cli"
    destination.mkdir()
    (destination / "previous.txt").write_text("preserve until validated", encoding="utf-8")
    monkeypatch.setattr(runtime, "_manifest", lambda: ("test", "https://example.invalid/runtime.zip", digest))
    monkeypatch.setattr(runtime, "urlopen", lambda *args, **kwargs: io.BytesIO(archive))
    verified = []
    monkeypatch.setattr(runtime, "_verify_runtime", verified.append)

    if valid_hash:
        runtime._repair_runtime(destination)
        assert (destination / "bin" / "az.cmd").is_file()
        assert not (destination / "previous.txt").exists()
        assert len(verified) == 1
    else:
        with pytest.raises(ValueError, match="SHA-256"):
            runtime._repair_runtime(destination)
        assert (destination / "previous.txt").is_file()
        assert verified == []
    assert list(tmp_path.iterdir()) == [destination]


def test_manifest_is_packaged_with_windows_build():
    spec = (Path(__file__).parents[1] / "FinOpsCCoE.spec").read_text(encoding="utf-8")

    assert '("windows-runtime.json", ".")' in spec


def test_healthy_runtime_starts_without_download_or_prompt(monkeypatch):
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime, "_verify_runtime", lambda _: None)

    def unexpected_prompt(*args, **kwargs):
        raise AssertionError("A complete installation must not request additional setup")

    monkeypatch.setattr("tkinter.messagebox.askyesno", unexpected_prompt)
    monkeypatch.setattr(runtime, "_repair_runtime", unexpected_prompt)

    assert runtime.ensure_windows_runtime() is True


def test_repair_rolls_back_if_final_replace_fails(monkeypatch, tmp_path):
    contents = io.BytesIO()
    with zipfile.ZipFile(contents, "w") as package:
        package.writestr("bin/az.cmd", "launcher")
    archive = contents.getvalue()
    destination = tmp_path / "azure-cli"
    destination.mkdir()
    (destination / "previous.txt").write_text("old runtime", encoding="utf-8")
    monkeypatch.setattr(
        runtime, "_manifest",
        lambda: ("test", "https://example.invalid/runtime.zip", hashlib.sha256(archive).hexdigest()),
    )
    monkeypatch.setattr(runtime, "urlopen", lambda *args, **kwargs: io.BytesIO(archive))
    monkeypatch.setattr(runtime, "_verify_runtime", lambda _: None)
    original_rename = Path.rename

    def fail_final_replace(path, target):
        if path.name == "new":
            raise OSError("Replacement blocked")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_final_replace)

    with pytest.raises(OSError, match="Replacement blocked"):
        runtime._repair_runtime(destination)
    assert (destination / "previous.txt").read_text(encoding="utf-8") == "old runtime"
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize("healthy", [False, True])
def test_installer_probe_returns_success_only_for_required_runtime(monkeypatch, tmp_path, healthy, capsys):
    launcher = tmp_path / "bin" / "az.cmd"
    launcher.parent.mkdir()
    launcher.touch()
    version, _, _ = runtime._manifest()
    monkeypatch.setattr(runtime.sys, "executable", str(tmp_path / "python.exe"))
    monkeypatch.setattr(runtime.sys, "argv", [runtime.__file__, str(runtime.RUNTIME_MANIFEST)])
    monkeypatch.setattr(
        runtime.subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, json.dumps({"azure-cli": version if healthy else "0.0.0"}), "",
        ),
    )

    if healthy:
        runpy.run_path(runtime.__file__, run_name="__main__")
    else:
        with pytest.raises(SystemExit) as error:
            runpy.run_path(runtime.__file__, run_name="__main__")
        assert error.value.code == 1
        assert "needs installation or repair" in capsys.readouterr().err
