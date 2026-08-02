"""Security helpers for document access and outbound URL validation."""

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import socket
import time
from urllib.parse import urlparse


_TOKEN_SECRET = os.getenv("DOCUMENT_TOKEN_SECRET") or secrets.token_urlsafe(32)
DOCUMENT_TOKEN_TTL = int(os.getenv("DOCUMENT_TOKEN_TTL_SECONDS", "3600"))


def create_document_token(filenames: list[str]) -> str:
    payload = {
        "files": sorted(set(filenames)),
        "exp": int(time.time()) + DOCUMENT_TOKEN_TTL,
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(_TOKEN_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def validate_document_token(token: str, filename: str) -> bool:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(_TOKEN_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        return int(payload.get("exp", 0)) >= int(time.time()) and filename in payload.get("files", [])
    except (ValueError, TypeError, json.JSONDecodeError):
        return False


def validate_public_https_url(url: str, allowed_hosts: set[str] | None = None) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTPS URLs are allowed")
    hostname = parsed.hostname.rstrip(".").lower()
    if allowed_hosts and hostname not in allowed_hosts and not any(hostname.endswith(f".{host}") for host in allowed_hosts):
        raise ValueError("URL host is not supported")
    addresses = {ipaddress.ip_address(hostname)} if _is_ip(hostname) else {
        ipaddress.ip_address(info[4][0]) for info in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    }
    if any(address.is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_reserved for address in addresses):
        raise ValueError("Private and local network URLs are not allowed")
    return parsed.geturl()


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False
