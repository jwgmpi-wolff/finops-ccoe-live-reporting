from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.request import urlopen
import zipfile


APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
RUNTIME_MANIFEST = APP_ROOT / "windows-runtime.json"


def runtime_directory() -> Path:
    return Path(sys.executable).resolve().parent / "azure-cli"


def authentication_environment(*, isolated: bool = False) -> dict[str, str]:
    environment = os.environ.copy()
    if isolated or getattr(sys, "frozen", False):
        profile = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FinOpsCCoE" / "azure"
        environment["AZURE_CONFIG_DIR"] = str(profile)
        environment["AZURE_EXTENSION_DIR"] = str(profile / "cliextensions")
        environment["AZURE_CORE_COLLECT_TELEMETRY"] = "no"
    environment["AZURE_CORE_ENABLE_BROKER_ON_WINDOWS"] = "false"
    environment["AZURE_CORE_LOGIN_EXPERIENCE_V2"] = "off"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def _manifest() -> tuple[str, str, str]:
    data = json.loads(RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or any(
        not isinstance(data.get(key), str) for key in ("version", "url", "sha256")
    ):
        raise ValueError("The authentication runtime manifest is invalid. Reinstall the Windows package.")
    if not data["url"].startswith("https://github.com/Azure/azure-cli/releases/download/"):
        raise ValueError("The authentication runtime download must use the official Azure CLI release.")
    return data["version"], data["url"], data["sha256"]


def _verify_runtime(directory: Path, *, isolated: bool = False) -> None:
    version, _, _ = _manifest()
    if not (directory / "bin" / "az.cmd").is_file():
        raise OSError("The bundled Microsoft sign-in launcher is missing.")
    environment = authentication_environment(isolated=isolated)
    environment["PATH"] = os.pathsep.join(
        (str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"),
         os.environ.get("SystemRoot", r"C:\Windows"))
    )
    result = subprocess.run(
        [str(directory / "python.exe"), "-IBm", "azure.cli", "version", "--output", "json"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=environment,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    if result.returncode != 0:
        raise OSError(f"The bundled sign-in runtime could not start: {result.stderr.strip()[-1000:]}")
    details = json.loads(result.stdout)
    if not isinstance(details, dict) or details.get("azure-cli") != version:
        raise ValueError(f"Microsoft sign-in requires the bundled runtime version {version}.")


def _repair_runtime(directory: Path) -> None:
    _, download_url, expected_hash = _manifest()
    if directory.is_symlink():
        raise OSError("Refusing to replace a linked authentication runtime directory.")
    with tempfile.TemporaryDirectory(prefix=".finops-runtime-", dir=directory.parent) as work:
        staging = Path(work)
        archive = staging / "runtime.zip"
        digest = hashlib.sha256()
        with urlopen(download_url, timeout=60) as response, archive.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest() != expected_hash:
            raise ValueError("The authentication runtime download failed SHA-256 verification.")
        extracted = staging / "new"
        with zipfile.ZipFile(archive) as package:
            package.extractall(extracted)
        _verify_runtime(extracted)
        backup = staging / "previous"
        if directory.exists():
            directory.rename(backup)
        try:
            extracted.rename(directory)
        except OSError:
            if backup.exists():
                backup.rename(directory)
            raise


def ensure_windows_runtime() -> bool:
    if not getattr(sys, "frozen", False):
        return True
    from tkinter import messagebox

    directory = runtime_directory()
    try:
        _verify_runtime(directory)
        return True
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        repair = messagebox.askyesno(
            "FinOps CCoE startup repair",
            f"Microsoft sign-in needs a component repaired or updated.\n\n{exc}\n\n"
            "Download and repair the official bundled runtime now? "
            "This downloads approximately 91 MB and does not install a system service or require administrator access.",
        )
    if not repair:
        return False
    try:
        _repair_runtime(directory)
        return True
    except (OSError, ValueError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        messagebox.showerror(
            "FinOps CCoE startup repair failed",
            f"The required component could not be repaired.\n\n{exc}\n\n"
            "Check your internet access or reinstall the latest complete Windows package.",
        )
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check an installed FinOps authentication runtime.")
    parser.add_argument("manifest", type=Path)
    arguments = parser.parse_args()
    RUNTIME_MANIFEST = arguments.manifest
    try:
        _verify_runtime(Path(sys.executable).resolve().parent, isolated=True)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Authentication runtime needs installation or repair: {error}", file=sys.stderr)
        raise SystemExit(1)
