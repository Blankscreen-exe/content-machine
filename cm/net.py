"""This machine's address on the local network."""
from __future__ import annotations

import socket
from functools import lru_cache


@lru_cache
def lan_ip() -> str:
    """The IP this machine would be reached at from elsewhere on the LAN.

    Cached: it doesn't change while the server is running, and every request that checks
    where it came from (see routes/local.py) would otherwise open a socket to find out.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))  # no packets are sent; this just picks the interface
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()
