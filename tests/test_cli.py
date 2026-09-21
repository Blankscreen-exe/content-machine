"""CLI behaviour that is easy to get wrong."""
from __future__ import annotations

import socket

from typer.testing import CliRunner

from cm.cli import _port_is_free, app

runner = CliRunner()


def test_port_in_use_is_reported_clearly():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]

        assert _port_is_free("127.0.0.1", port) is False

        result = runner.invoke(app, ["serve", "--port", str(port), "--no-open"])
        assert result.exit_code == 1
        assert "already in use" in result.output
        assert f"--port {port + 1}" in result.output      # tells you what to do next


def test_free_port_is_reported_free():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    assert _port_is_free("127.0.0.1", port) is True
