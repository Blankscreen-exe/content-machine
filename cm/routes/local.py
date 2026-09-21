"""Whether a request comes from the machine running the app.

The app can be served on the local network (`cm serve --lan`) so a phone or another
computer can use it. Starting programs or opening windows is only allowed for requests
from this machine itself: nothing on the network should be able to do that here, and a
window opened here would not be seen by someone on another device anyway.
"""
from __future__ import annotations

from fastapi import Request

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def from_this_machine(request: Request) -> bool:
    return request.client is not None and request.client.host in LOCAL_HOSTS
