"""Shared network utilities for normalizing Docker service URLs."""

import os
from urllib.parse import urlsplit, urlunsplit


def _rewrite_service_hostname(url: str, service_name: str, ip_address: str) -> str:
    """Rewrite a URL's hostname if it matches a Docker service name."""
    if not url:
        return url

    parts = urlsplit(url)
    if parts.hostname != service_name:
        return url

    netloc = ip_address
    if parts.username:
        credentials = parts.username
        if parts.password:
            credentials = f"{credentials}:{parts.password}"
        netloc = f"{credentials}@{netloc}"
    if parts.port:
        netloc = f"{netloc}:{parts.port}"

    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def normalize_container_service_urls(url: str) -> str:
    """Rewrite Docker service hostnames to static IPs when running behind Gluetun."""
    if os.environ.get("GLUETUN_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return url

    normalized = _rewrite_service_hostname(url, "db", "172.30.0.3")
    normalized = _rewrite_service_hostname(normalized, "redis", "172.30.0.4")
    return normalized
