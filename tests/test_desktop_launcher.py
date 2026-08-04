import socket

from desktop_launcher import HOST, _reserve_open_port


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