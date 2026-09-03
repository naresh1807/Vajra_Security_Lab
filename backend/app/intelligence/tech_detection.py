"""
Shared technology-fingerprinting heuristics (Section 41's "Show Underlying
Tool" spirit - simple and easy to extend, not a full fingerprint database).

Used by both the recon engine (live-host probing) and the HTTP Inspector
(manual request/response capture) so a host looks the same regardless of
which module discovered it.
"""
from __future__ import annotations

import httpx

_TECH_HINTS: list[tuple[str, str]] = [
    ("cloudflare", "Cloudflare"),
    ("nginx", "nginx"),
    ("apache", "Apache"),
    ("microsoft-iis", "IIS"),
    ("express", "Express"),
    ("gunicorn", "Gunicorn"),
    ("kestrel", "Kestrel/.NET"),
    ("varnish", "Varnish"),
]


def detect_technologies(headers: httpx.Headers, body_lower: str) -> list[str]:
    found: set[str] = set()
    haystack = f"{(headers.get('server') or '').lower()} {(headers.get('x-powered-by') or '').lower()}"
    for hint, label in _TECH_HINTS:
        if hint in haystack:
            found.add(label)
    if "wp-content" in body_lower or "wordpress" in body_lower:
        found.add("WordPress")
    if "__next" in body_lower or "_next/static" in body_lower:
        found.add("Next.js")
    if "react" in body_lower:
        found.add("React")
    return sorted(found)
