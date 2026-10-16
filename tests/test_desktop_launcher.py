import socket

import desktop_launcher
from desktop_launcher import (
    HOST,
    _open_existing_instance,
    _report_url,
    _reserve_open_port,
    _write_instance_port,
)


def test_reserve_open_port_returns_distinct_listening_ports():
    first_listener, first_port = _reserve_open_port()
    second_listener, second_port = _reserve_open_port()
    try:
        assert first_port > 0
        assert second_port > 0
        assert first_port != second_port

        with socket.create_connection((HOST, first_port), timeout=1):
            pass
        with socket.create_connection((HOST, second_port), timeout=1):
            pass
    finally:
        first_listener.close()
        second_listener.close()


def test_report_url_uses_reserved_port():
    assert _report_url(54321) == (
        "http://127.0.0.1:54321/api/run_finops_report?format=html&page=1&pageSize=25"
    )


def test_instance_port_is_published_atomically(tmp_path, monkeypatch):
    port_file = tmp_path / "instance.port"
    monkeypatch.setattr(desktop_launcher, "INSTANCE_PORT_FILE", port_file)

    _write_instance_port(54321)

    assert port_file.read_text(encoding="ascii") == "54321"
    assert list(tmp_path.glob("*.tmp")) == []


def test_existing_instance_ignores_stale_port(tmp_path, monkeypatch):
    port_file = tmp_path / "instance.port"
    port_file.write_text("54321", encoding="ascii")
    opened = []
    monkeypatch.setattr(desktop_launcher, "INSTANCE_PORT_FILE", port_file)
    monkeypatch.setattr(
        desktop_launcher.socket,
        "create_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("not listening")),
    )
    monkeypatch.setattr(desktop_launcher.webbrowser, "open", opened.append)

    _open_existing_instance()

    assert opened == []


def test_browser_waits_for_healthy_service_not_just_a_listening_socket(monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace

    responses = iter([503, 200])
    opened = []
    probes = []

    def fake_urlopen(url, **kwargs):
        probes.append(url)
        return nullcontext(SimpleNamespace(status=next(responses)))

    monkeypatch.setattr(desktop_launcher, "urlopen", fake_urlopen)
    monkeypatch.setattr(desktop_launcher.webbrowser, "open", opened.append)

    desktop_launcher._open_report_when_ready(54321)

    assert probes == ["http://127.0.0.1:54321/api/health"] * 2
    assert opened == [desktop_launcher._report_url(54321)]


def test_startup_stops_when_required_component_repair_is_declined(monkeypatch):
    monkeypatch.setattr(desktop_launcher, "_acquire_instance_mutex", lambda: 1)
    monkeypatch.setattr(desktop_launcher, "ensure_windows_runtime", lambda: False)

    def must_not_start():
        raise AssertionError("Do not start a partially configured application")

    monkeypatch.setattr(desktop_launcher, "_reserve_open_port", must_not_start)

    desktop_launcher.main()
