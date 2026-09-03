from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.projects.models import Project
from app.scopeguard.engine import check_scope
from app.scopeguard.models import ScopeDecision

DESTRUCTIVE_SEGMENTS = {
    "logout", "log-out", "signout", "sign-out", "delete", "remove", "destroy",
    "reset", "unsubscribe", "terminate", "deactivate", "close-account", "cancel-account",
}
SENSITIVE_QUERY = re.compile(r"(?i)(token|secret|password|passwd|key|session|auth|code|jwt)")


@dataclass(frozen=True)
class SafeEndpoint:
    url: str
    normalized_url: str
    hostname: str
    path: str
    query_parameters: list[str]


def destructive_path_reason(path: str) -> str | None:
    segments = {segment.lower() for segment in path.split("/") if segment}
    matched = sorted(segments & DESTRUCTIVE_SEGMENTS)
    return f"Path contains a destructive or session-changing segment: {matched[0]}" if matched else None


def sanitize_endpoint_url(
    project: Project,
    raw_url: str,
    *,
    allow_destructive_path: bool = False,
) -> tuple[SafeEndpoint | None, str | None]:
    try:
        parts = urlsplit(raw_url.strip())
        port = parts.port
    except ValueError:
        return None, "URL could not be parsed safely."
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None, "Only absolute HTTP(S) URLs are accepted."
    if parts.username is not None or parts.password is not None:
        return None, "URLs containing embedded credentials are rejected."
    scope = check_scope(project, parts.hostname)
    if scope.decision != ScopeDecision.ALLOWED:
        return None, f"ScopeGuard rejected the discovered host: {scope.reason}"
    if not allow_destructive_path:
        reason = destructive_path_reason(parts.path or "/")
        if reason:
            return None, reason

    query = parse_qsl(parts.query, keep_blank_values=True)
    names = sorted({key for key, _ in query})
    redacted_query = sorted(
        (key, "[REDACTED]" if SENSITIVE_QUERY.search(key) else value)
        for key, value in query
    )
    host = parts.hostname.lower().rstrip(".")
    default_port = (parts.scheme.lower() == "https" and port == 443) or (parts.scheme.lower() == "http" and port == 80)
    netloc = host if port is None or default_port else f"{host}:{port}"
    path = parts.path or "/"
    safe_url = urlunsplit((parts.scheme.lower(), netloc, path, urlencode(redacted_query, doseq=True), ""))
    normalized_query = urlencode([(name, "") for name in names])
    normalized_url = urlunsplit((parts.scheme.lower(), netloc, path, normalized_query, ""))
    return SafeEndpoint(safe_url, normalized_url, host, path, names), None


def redact_url_for_log(raw_url: str) -> str:
    try:
        parts = urlsplit(raw_url)
        query = [
            (key, "[REDACTED]" if SENSITIVE_QUERY.search(key) else value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
        ]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))[:2000]
    except ValueError:
        return raw_url.split("?", 1)[0][:2000]
