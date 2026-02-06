"""Validation helpers for uploads and URLs."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException


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
            raise HTTPException(status_code=400, detail="File must be UTF-8 text") from exc


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="URL scheme must be http or https")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="URL must include a host")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="URL credentials are not allowed")

    hostname = parsed.hostname.lower()
    if hostname in {"localhost"} or hostname.endswith(".local"):
        raise HTTPException(status_code=400, detail="URL host is not allowed")

    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="URL host could not be resolved") from exc

    for _, _, _, _, sockaddr in addr_info:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise HTTPException(status_code=400, detail="URL host is not allowed")
