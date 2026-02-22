"""Validation helpers for uploads and URLs."""

from __future__ import annotations

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException

# Well-known IPv6 prefixes for private / link-local addresses
_IPV6_PRIVATE_PREFIXES = ("fe80:", "fc00:", "fd00:")


def _is_private_ip(ip_str: str) -> bool:
    """Return True if *ip_str* resolves to a non-public IP address.

    Checks the standard library properties: is_private, is_loopback,
    is_link_local, is_multicast, is_reserved, and is_unspecified.
    Also explicitly blocks well-known IPv6 private prefixes.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        # If it cannot be parsed as an IP at all, treat it as unsafe.
        return True

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True

    # Explicit IPv6 private-range check (belt-and-suspenders)
    lower = ip_str.lower()
    if lower == "::1" or lower.startswith(_IPV6_PRIVATE_PREFIXES):
        return True

    return False


def validate_upload(contents: bytes, filename: str, settings: dict[str, Any]) -> None:
    if len(contents) > settings["MAX_CONTENT_LENGTH"]:
        raise HTTPException(status_code=413, detail="File too large")

    extension = filename.rsplit(".", 1)[1].lower()
    if extension == "pdf":
        if not contents.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="Invalid PDF upload")
    else:
        try:
            contents.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=400, detail="File must be UTF-8 text"
            ) from exc


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="URL scheme must be http or https")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="URL must include a host")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="URL credentials are not allowed")

    # --- Port restriction: only 80 and 443 are allowed ---
    if parsed.port is not None and parsed.port not in {80, 443}:
        raise HTTPException(
            status_code=400,
            detail="URL port is not allowed (only 80 and 443 are permitted)",
        )

    # Case-insensitive hostname checks
    hostname = parsed.hostname.lower()
    if hostname in {"localhost"} or hostname.endswith(".local"):
        raise HTTPException(status_code=400, detail="URL host is not allowed")

    # Block IPv6 private addresses supplied directly as hostnames
    if hostname == "::1" or hostname.startswith(_IPV6_PRIVATE_PREFIXES):
        raise HTTPException(status_code=400, detail="URL host is not allowed")

    # Run DNS resolution in a thread pool with a timeout to prevent
    # DNS-based slowloris attacks (blocking indefinitely on a slow resolver).
    _DNS_TIMEOUT_SECONDS = 5
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                socket.getaddrinfo,
                hostname,
                parsed.port or 443,
                type=socket.SOCK_STREAM,
            )
            addr_info = future.result(timeout=_DNS_TIMEOUT_SECONDS)
    except FuturesTimeoutError as exc:
        raise HTTPException(
            status_code=400,
            detail="URL host could not be resolved (DNS timeout)",
        ) from exc
    except socket.gaierror as exc:
        raise HTTPException(
            status_code=400, detail="URL host could not be resolved"
        ) from exc

    for _, _, _, _, sockaddr in addr_info:
        if _is_private_ip(sockaddr[0]):
            raise HTTPException(status_code=400, detail="URL host is not allowed")
