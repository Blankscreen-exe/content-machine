"""A browser hanging up, which Python's event loop on Windows reports as an error.

When a browser drops a connection (a video that seeks abandons its request, a tab closes),
the event loop Windows uses may try to shut the socket down after the browser has already
reset it. It then logs the ConnectionResetError from `_call_connection_lost` with a full
traceback, although nothing failed: the request was already over. A console full of those
hides the errors that matter, so exactly that report is dropped, and every other error is
reported as before.
"""
from __future__ import annotations

import asyncio


def is_client_hangup(context: dict) -> bool:
    """Whether an event loop error report is only the browser having hung up first."""
    return (isinstance(context.get("exception"), ConnectionResetError)
            and "_call_connection_lost" in repr(context.get("handle")))


def ignore_client_hangups(loop: asyncio.AbstractEventLoop) -> None:
    """Have `loop` stay quiet about browsers hanging up, passing every other error on to
    whatever handled them before."""
    previous = loop.get_exception_handler()

    def handle(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        if is_client_hangup(context):
            return
        if previous:
            previous(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(handle)
