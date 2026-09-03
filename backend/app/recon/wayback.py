"""
Passive URL discovery from the Internet Archive's Wayback Machine (Section 7,
"URL DISCOVERY" / "PARAMETER DISCOVERY").

Like crt.sh, this is an OSINT lookup: it queries the public Wayback CDX
index of pages the Internet Archive has *already* crawled, and never
sends the target a request. Every URL it returns still passes through
ScopeGuard (via `sanitize_endpoint_url`) before it is stored, and none
is ever fetched - historical URLs become inventory entries and
parameter-intelligence input, nothing more.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

from app.core.config import settings
from app.scopeguard.engine import normalize_target

_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I
)


@dataclass
class WaybackDiscovery:
    urls: list[str] = field(default_factory=list)
    available: bool = False
    error: str | None = None


def parse_cdx_output(text: str, domain: str, limit: int) -> list[str]:
    """One `original` URL per line (output=text, fl=original). Keep HTTP(S),
    on the target domain or a subdomain, de-duplicated, capped at `limit`."""
    root = normalize_target(domain)
    urls: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate or not candidate.lower().startswith(("http://", "https://")):
            continue
        host = normalize_target(candidate)
        if not host or not (host == root or host.endswith(f".{root}")):
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        urls.append(candidate)
        if len(urls) >= limit:
            break
    return urls


async def discover_wayback_urls(domain: str) -> WaybackDiscovery:
    if not settings.wayback_enabled:
        return WaybackDiscovery(error="Wayback URL discovery is disabled by configuration.")
    root = normalize_target(domain)
    if not _DOMAIN_RE.fullmatch(root):
        return WaybackDiscovery(error="Project target is not a valid DNS domain for a Wayback lookup.")

    params = {
        "url": f"{root}/*",
        "matchType": "domain",  # the domain and every subdomain
        "output": "text",
        "fl": "original",
        "collapse": "urlkey",  # Wayback-side de-duplication
        "limit": str(settings.wayback_max_urls),
    }
    try:
        async with httpx.AsyncClient(
            timeout=settings.wayback_timeout_seconds,
            headers={"User-Agent": settings.http_user_agent},
            follow_redirects=True,
        ) as client:
            resp = await client.get(settings.wayback_cdx_url, params=params)
            resp.raise_for_status()
            body = resp.content
    except Exception as exc:  # noqa: BLE001 - a flaky archive shouldn't fail the recon run
        return WaybackDiscovery(available=True, error=f"Wayback CDX lookup failed: {exc}")

    if len(body) > settings.wayback_max_response_bytes:
        return WaybackDiscovery(
            available=True,
            error=f"Wayback CDX response exceeded the {settings.wayback_max_response_bytes}-byte safety limit.",
        )

    text = body.decode("utf-8", errors="replace")
    return WaybackDiscovery(
        urls=parse_cdx_output(text, root, settings.wayback_max_urls), available=True
    )
