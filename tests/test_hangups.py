"""A browser hanging up is not reported as an error; every real error still is."""
from __future__ import annotations

import asyncio

import pytest

from cm.hangups import ignore_client_hangups, is_client_hangup


class Handle:
    """Stands in for the event loop's handle, which names the callback that failed."""

    def __init__(self, callback: str) -> None:
        self.callback = callback

    def __repr__(self) -> str:
        return f"<Handle {self.callback}()>"


HANGUP = {"message": "Exception in callback _ProactorBasePipeTransport._call_connection_lost()",
          "exception": ConnectionResetError(10054, "An existing connection was forcibly closed by the remote host"),
          "handle": Handle("_ProactorBasePipeTransport._call_connection_lost")}


@pytest.fixture
def loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _reported(loop, monkeypatch, context) -> list[dict]:
    reports = []
    monkeypatch.setattr(loop, "default_exception_handler", reports.append)
    ignore_client_hangups(loop)
    loop.call_exception_handler(context)
    return reports


def test_the_browser_hanging_up_first_is_not_reported(loop, monkeypatch):
    assert is_client_hangup(HANGUP)
    assert _reported(loop, monkeypatch, HANGUP) == []


@pytest.mark.parametrize("context", [
    {"message": "a reset somewhere else", "exception": ConnectionResetError(),
     "handle": Handle("SomeProtocol.data_received")},
    {"message": "a real fault in the same place", "exception": OSError("disk full"),
     "handle": Handle("_ProactorBasePipeTransport._call_connection_lost")},
    {"message": "no exception at all", "handle": Handle("_ProactorBasePipeTransport._call_connection_lost")},
])
def test_every_other_error_is_still_reported(loop, monkeypatch, context):
    assert _reported(loop, monkeypatch, context) == [context]


def test_a_handler_already_in_place_still_gets_the_rest(loop):
    earlier = []
    loop.set_exception_handler(lambda loop, context: earlier.append(context))
    ignore_client_hangups(loop)
    real = {"message": "a real fault", "exception": RuntimeError("boom")}
    loop.call_exception_handler(HANGUP)
    loop.call_exception_handler(real)
    assert earlier == [real]
