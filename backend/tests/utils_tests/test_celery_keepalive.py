"""TCP keepalive options for broker connections must use this platform's option numbers.

With the Linux ints hard-coded, redis-py's setsockopt failed with ENOPROTOOPT on macOS and
the worker could never reach the broker.
"""

import socket
from types import SimpleNamespace

import pytest

from app.integrations.celery import core as celery_core
from app.main import celery_app


class TestTcpKeepaliveOptions:
    def test_linux_numbers_are_unchanged(self, monkeypatch: pytest.MonkeyPatch) -> None:
        linux = SimpleNamespace(TCP_KEEPIDLE=4, TCP_KEEPINTVL=5, TCP_KEEPCNT=6)
        monkeypatch.setattr(celery_core, "socket", linux)

        assert celery_core._tcp_keepalive_options() == {4: 60, 5: 10, 6: 3}

    def test_macos_sets_the_idle_time_through_tcp_keepalive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        macos = SimpleNamespace(TCP_KEEPALIVE=0x10, TCP_KEEPINTVL=0x101, TCP_KEEPCNT=0x102)
        monkeypatch.setattr(celery_core, "socket", macos)

        assert celery_core._tcp_keepalive_options() == {0x10: 60, 0x101: 10, 0x102: 3}

    def test_options_the_platform_lacks_are_left_out(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(celery_core, "socket", SimpleNamespace(TCP_KEEPINTVL=5))

        assert celery_core._tcp_keepalive_options() == {5: 10}

    def test_broker_options_are_accepted_by_this_platform(self) -> None:
        transport_options = celery_app.conf.broker_transport_options
        assert transport_options["socket_keepalive"] is True
        options = transport_options["socket_keepalive_options"]
        assert options

        # Same calls redis-py makes before connecting to the broker.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            for option, value in options.items():
                sock.setsockopt(socket.IPPROTO_TCP, option, value)
