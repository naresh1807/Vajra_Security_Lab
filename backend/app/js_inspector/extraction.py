"""
Vajra JS Intelligence (Section 19) - regex-based extraction over fetched
JavaScript source. Deliberately simple pattern matching, not a JS parser -
easy to read, easy to extend, and transparent about what it can miss.

Every potential secret is masked before it is ever returned or stored -
"Potential credentials must be masked" and "Never automatically use
credentials" (Section 19) are treated as hard requirements here, not
suggestions: `mask_secret` is applied at extraction time, so the raw
value never even reaches the caller, let alone the database.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.masking import mask_secret

_ROUTE_RE = re.compile(r"""["'](/(?:api|graphql|v[0-9]+|admin|internal)[a-zA-Z0-9_\-/{}.:]*)["']""")
_GENERIC_PATH_RE = re.compile(r"""["'](/[a-zA-Z][a-zA-Z0-9_\-]*(?:/[a-zA-Z0-9_\-{}.:]+){1,6})["']""")
_STATIC_EXT_RE = re.compile(r"\.(png|jpe?g|gif|svg|css|woff2?|ttf|eot|ico|map)(\?|$)", re.IGNORECASE)

_GRAPHQL_URL_RE = re.compile(r"""["'](https?://[^"']*graphql[^"']*)["']""", re.IGNORECASE)
_WS_URL_RE = re.compile(r"""["'](wss?://[^"']+)["']""")
_SOURCE_MAP_RE = re.compile(r"//[#@]\s*sourceMappingURL=(\S+)")

_CONFIG_KEY_RE = re.compile(
    r"""\b([A-Za-z_][A-Za-z0-9_]*(?:BASE[_-]?URL|API[_-]?URL|ENDPOINT|BASE_PATH))\s*[:=]\s*["']([^"']{3,200})["']"""
)

_SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("AWS Access Key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API Key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("Slack Token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,48}\b")),
    ("JWT-like Token", re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")),
    ("Private Key Block", re.compile(r"-----BEGIN(?: RSA| EC| OPENSSH)? PRIVATE KEY-----")),
    (
        "Generic API Key/Secret Assignment",
        re.compile(
            r"""(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|client[_-]?secret)\b\s*[:=]\s*["']([a-zA-Z0-9_\-]{12,})["']"""
        ),
    ),
]


@dataclass
class SecretFinding:
    label: str
    masked_value: str
    context: str


def _mask_in_context(context: str, raw: str) -> str:
    return context.replace(raw, mask_secret(raw)) if raw in context else context


def extract_api_routes(js_text: str) -> set[str]:
    routes: set[str] = set()
    for pattern in (_ROUTE_RE, _GENERIC_PATH_RE):
        for match in pattern.finditer(js_text):
            path = match.group(1)
            if _STATIC_EXT_RE.search(path):
                continue
            routes.add(path)
    return routes


def extract_graphql_urls(js_text: str) -> set[str]:
    return {m.group(1) for m in _GRAPHQL_URL_RE.finditer(js_text)}


def extract_websocket_urls(js_text: str) -> set[str]:
    return {m.group(1) for m in _WS_URL_RE.finditer(js_text)}


def extract_source_maps(js_text: str) -> set[str]:
    return {m.group(1) for m in _SOURCE_MAP_RE.finditer(js_text)}


def extract_config_references(js_text: str) -> dict[str, str]:
    refs: dict[str, str] = {}
    for match in _CONFIG_KEY_RE.finditer(js_text):
        refs[match.group(1)] = match.group(2)
    return refs


def extract_potential_secrets(js_text: str) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    seen: set[str] = set()
    for label, pattern in _SECRET_PATTERNS:
        for match in pattern.finditer(js_text):
            raw = match.group(1) if match.groups() else match.group(0)
            if raw in seen:
                continue
            seen.add(raw)
            start = max(match.start() - 20, 0)
            end = min(match.end() + 20, len(js_text))
            context = _mask_in_context(js_text[start:end].replace("\n", " ").strip(), raw)
            findings.append(SecretFinding(label=label, masked_value=mask_secret(raw), context=context))
    return findings
