"""Whether a request comes from the machine running the app.

The app can be served on the local network (`cm serve --lan`) so a phone or another
computer can use it. Starting programs or opening windows is only allowed for requests
from this machine itself: nothing on the network should be able to do that here, and a
window opened here would not be seen by someone on another device anyway.

Opening the --lan link on this same machine still counts as local: the OS then routes
the connection through the LAN interface, so it arrives as this machine's own LAN
address rather than as loopback.
"""
from __future__ import annotations

from fastapi import Request

from ..net import lan_ip

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def from_this_machine(request: Request) -> bool:
    if request.client is None:
        return False
    return request.client.host in LOCAL_HOSTS or request.client.host == lan_ip()


def opened_at_loopback(request: Request) -> bool:
    """Whether the page was opened at a loopback address, such as http://localhost:8777.

    A browser only lets a page use the microphone on a secure address, and over plain
    http only loopback counts. So the --lan link, even opened on this machine, cannot
    record: this looks at the address the browser used, not where the request came from.
    """
    return request.url.hostname in LOCAL_HOSTS
