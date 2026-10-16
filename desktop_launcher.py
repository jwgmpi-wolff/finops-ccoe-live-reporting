from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import socket
import threading
import time
import webbrowser
from tkinter import messagebox
from urllib.error import URLError
from urllib.request import urlopen

from app.desktop_runtime import ensure_windows_runtime


HOST = "127.0.0.1"
STARTUP_TIMEOUT_SECONDS = 120
INSTANCE_MUTEX_NAME = "Local\\FinOpsCCoELiveReporting"
INSTANCE_PORT_FILE = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FinOpsCCoE" / "instance.port"
ERROR_ALREADY_EXISTS = 183


def _reserve_open_port() -> tuple[socket.socket, int]:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind((HOST, 0))
    listener.listen()
    return listener, listener.getsockname()[1]


def _open_report_when_ready(port: int) -> None:
    report_url = f"http://{HOST}:{port}/api/run_finops_report?format=html&page=1&pageSize=25"
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://{HOST}:{port}/api/health", timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(report_url)
                    return
        except (OSError, URLError):
            time.sleep(0.5)


def _report_url(port: int) -> str:
    return f"http://{HOST}:{port}/api/run_finops_report?format=html&page=1&pageSize=25"


def _write_instance_port(port: int) -> None:
    INSTANCE_PORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = INSTANCE_PORT_FILE.with_suffix(f".{os.getpid()}.tmp")
    temporary_file.write_text(str(port), encoding="ascii")
    os.replace(temporary_file, INSTANCE_PORT_FILE)


def _acquire_instance_mutex() -> int | None:
    if os.name != "nt":
        return 1
    create_mutex = ctypes.windll.kernel32.CreateMutexW
    create_mutex.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    create_mutex.restype = wintypes.HANDLE
    handle = create_mutex(None, False, INSTANCE_MUTEX_NAME)
    if not handle:
        return None
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        ctypes.windll.kernel32.CloseHandle(handle)
        return None
    return handle


def _open_existing_instance() -> None:
    try:
        port = int(INSTANCE_PORT_FILE.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return
    if not 1 <= port <= 65535:
        return
    try:
        with socket.create_connection((HOST, port), timeout=1):
            pass
    except OSError:
        return
    webbrowser.open(_report_url(port))


def main() -> None:
    instance_mutex = _acquire_instance_mutex()
    if instance_mutex is None:
        _open_existing_instance()
        return

    startup_ready = False
    try:
        import uvicorn
        from app.main import app

        if not ensure_windows_runtime():
            return
        startup_ready = True
    except (ImportError, OSError, ValueError) as exc:
        repair = messagebox.askyesno(
            "FinOps CCoE startup failed",
            f"A required application component could not start.\n\n{exc}\n\n"
            "Open the latest complete Windows installer download to repair or update the application? "
            "Private repository downloads require GitHub sign-in.",
        )
        if repair:
            webbrowser.open(
                "https://github.com/jwgmpi-wolff/finops-ccoe-live-reporting/releases/latest/download/FinOpsCCoE-Setup.exe"
            )
        return
    finally:
        if not startup_ready and os.name == "nt" and instance_mutex != 1:
            ctypes.windll.kernel32.CloseHandle(instance_mutex)

    INSTANCE_PORT_FILE.unlink(missing_ok=True)
    try:
        listener, port = _reserve_open_port()
    except OSError as exc:
        messagebox.showerror(
            "FinOps CCoE Live Reporting",
            f"The application could not reserve a local port.\n\n{exc}",
        )
        if os.name == "nt" and instance_mutex != 1:
            ctypes.windll.kernel32.CloseHandle(instance_mutex)
        return

    _write_instance_port(port)
    threading.Thread(target=_open_report_when_ready, args=(port,), daemon=True).start()
    try:
        config = uvicorn.Config(
            app,
            host=HOST,
            port=port,
            log_config=None,
            access_log=False,
        )
        uvicorn.Server(config).run(sockets=[listener])
    except Exception as exc:
        messagebox.showerror(
            "FinOps CCoE Live Reporting",
            f"The application could not start.\n\n{exc}",
        )
    finally:
        listener.close()
        INSTANCE_PORT_FILE.unlink(missing_ok=True)
        if os.name == "nt" and instance_mutex != 1:
            ctypes.windll.kernel32.CloseHandle(instance_mutex)


if __name__ == "__main__":
    main()