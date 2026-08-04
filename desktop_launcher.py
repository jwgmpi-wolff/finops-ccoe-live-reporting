from __future__ import annotations

import socket
import threading
import time
import webbrowser
from tkinter import messagebox

import uvicorn

from app.main import app


HOST = "127.0.0.1"
STARTUP_TIMEOUT_SECONDS = 120


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
            with socket.create_connection((HOST, port), timeout=1):
                webbrowser.open(report_url)
                return
        except OSError:
            time.sleep(0.5)


def main() -> None:
    try:
        listener, port = _reserve_open_port()
    except OSError as exc:
        messagebox.showerror(
            "FinOps CCoE Live Reporting",
            f"The application could not reserve a local port.\n\n{exc}",
        )
        return

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


if __name__ == "__main__":
    main()