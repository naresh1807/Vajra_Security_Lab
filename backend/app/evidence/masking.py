"""
Evidence masking (Section 31): "Mask cookies, bearer tokens, passwords,
sensitive credentials." Applied whenever a transaction is packaged as
evidence (Evidence Vault, Report Generator) - never in the HTTP Inspector
itself, where seeing the real value is the entire point of inspecting.
"""
from __future__ import annotations

import json
import re

from app.core.masking import mask_secret

_SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "proxy-authorization",
}

_SENSITIVE_BODY_KEY_RE = re.compile(
    r'"(password|pwd|passwd|secret|token|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret)"'
    r'\s*:\s*"([^"]*)"',
    re.IGNORECASE,
)


def mask_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: (mask_secret(v) if k.lower() in _SENSITIVE_HEADER_NAMES and v else v) for k, v in headers.items()}


def mask_cookies(cookies: list[str]) -> list[str]:
    masked: list[str] = []
    for raw in cookies:
        if "=" not in raw:
            masked.append(raw)
            continue
        name, rest = raw.split("=", 1)
        value, sep, attrs = rest.partition(";")
        masked.append(f"{name}={mask_secret(value)}{sep}{attrs}")
    return masked


def mask_body(body: str | None) -> str | None:
    if not body:
        return body
    return _SENSITIVE_BODY_KEY_RE.sub(lambda m: f'"{m.group(1)}": "{mask_secret(m.group(2))}"', body)


def is_masking_verifiable(body: str | None) -> bool:
    """True when the body is valid JSON (so key-based masking definitely
    matched real keys) or empty. False for non-JSON bodies, where the
    regex-based masking above is best-effort, not guaranteed complete -
    the Report Readiness score should not blindly award full credit for
    masking it can't verify.
    """
    if not body:
        return True
    try:
        json.loads(body)
        return True
    except (ValueError, TypeError):
        return False
