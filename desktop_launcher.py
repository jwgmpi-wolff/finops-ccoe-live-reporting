from __future__ import annotations

import socket
import threading
import time
import webbrowser
from tkinter import messagebox

import uvicorn

from app.main import app


HOST = "127.0.0.1"
PORT = 8010
REPORT_URL = f"http://{HOST}:{PORT}/api/run_finops_report?format=html&page=1&pageSize=25"
STARTUP_TIMEOUT_SECONDS = 120


def _port_is_available() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((HOST, PORT))
        except OSError:
            return False
    return True


def _open_report_when_ready() -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=1):
                webbrowser.open(REPORT_URL)
                return
        except OSError:
            time.sleep(0.5)


def main() -> None:
    if not _port_is_available():
        messagebox.showerror(
            "FinOps CCoE Live Reporting",
            f"Port {PORT} is already in use. Close the other local service and try again.",
        )
        return

    threading.Thread(target=_open_report_when_ready, daemon=True).start()
    try:
        uvicorn.run(
            app,
            host=HOST,
            port=PORT,
            log_config=None,
            access_log=False,
        )
    except Exception as exc:
        messagebox.showerror(
            "FinOps CCoE Live Reporting",
            f"The application could not start.\n\n{exc}",
        )


if __name__ == "__main__":
    main()