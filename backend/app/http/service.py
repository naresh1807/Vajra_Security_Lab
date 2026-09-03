"""
Vajra HTTP Inspector (Section 12-13) - MVP implementation.

Every manually-sent request goes through the exact same ScopeGuard check
and per-project rate limiter as the recon engine (Section 5: "No security
module should bypass ScopeGuard") - it shares the same rate-limiter
instance, so manual HTTP Inspector traffic and background recon traffic
against the same project are throttled together, not independently.

The `interesting_indicators` stored on each transaction are a flat,
at-a-glance summary computed by running the full Vajra Analyzer (Section
22, `app.analyzer.checks`) and keeping only non-informational findings -
there's a single source of truth for "what's interesting about this
response", not two copies of the same logic.
"""
from __future__ import annotations

import asyncio
import time
from urllib.parse import urlsplit

import httpx
from sqlalchemy.orm import Session

from app.analyzer.checks import AnalyzerInput, Classification, run_all_analyzers
from app.core.config import settings
from app.core.outbound import request_with_safe_redirects
from app.intelligence.tech_detection import detect_technologies
from app.projects.models import Project
from app.scopeguard.engine import check_scope, rate_limiter
from app.scopeguard.models import ScopeAuditLog, ScopeDecision

MAX_STORED_BODY_CHARS = 50_000


class ScopeBlockedError(Exception):
    def __init__(self, reason: str, decision: ScopeDecision):
        super().__init__(reason)
        self.reason = reason
        self.decision = decision


def _summarize_indicators(
    url: str, status_code: int, request_headers: dict[str, str], response_headers: dict[str, str],
    response_cookies: list[str], body: str,
) -> list[str]:
    data = AnalyzerInput(
        url=url,
        status_code=status_code,
        request_headers=request_headers,
        response_headers=response_headers,
        response_cookies=response_cookies,
        body=body,
    )
    findings = run_all_analyzers(data)
    return [f.title for f in findings if f.classification != Classification.INFORMATIONAL]


async def send_http_request(
    db: Session,
    project: Project,
    method: str,
    url: str,
    headers: dict[str, str],
    body: str | None,
    *,
    sensitive_header_names: set[str] | None = None,
) -> dict:
    """Returns a dict of fields ready to construct an HttpTransaction row.

    Every attempt - allowed or blocked - is logged to the ScopeAuditLog
    before anything else happens. Raises ScopeBlockedError if the target
    isn't ALLOWED; the router turns that into an HTTP 403 with the reason.
    """
    host = urlsplit(url if "://" in url else f"//{url}").hostname or ""
    result = check_scope(project, host or url)

    db.add(
        ScopeAuditLog(
            project_id=project.id,
            target_input=url,
            normalized_target=result.normalized_target,
            decision=result.decision,
            reason=result.reason,
            operation="http_inspector_manual_request",
        )
    )
    db.commit()

    if result.decision != ScopeDecision.ALLOWED:
        raise ScopeBlockedError(result.reason, result.decision)

    while not rate_limiter.allow(project.id, project.rate_limit_rps):
        await asyncio.sleep(1.0 / max(project.rate_limit_rps, 0.1))

    fields: dict = {
        "method": method.upper(),
        "url": url,
        "request_headers": headers,
        "request_body": body,
        "status_code": None,
        "response_headers": {},
        "response_cookies": [],
        "response_body": None,
        "response_body_truncated": False,
        "response_size_bytes": None,
        "timing_ms": None,
        "technologies": [],
        "interesting_indicators": [],
        "error": None,
    }

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_seconds, headers={"User-Agent": settings.http_user_agent}, follow_redirects=False
        ) as client:
            resp = await request_with_safe_redirects(
                client,
                project,
                method,
                url,
                headers=headers,
                content=body,
                sensitive_header_names=sensitive_header_names,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000

        raw_body = resp.text or ""
        truncated = len(raw_body) > MAX_STORED_BODY_CHARS
        stored_body = raw_body[:MAX_STORED_BODY_CHARS]
        body_lower = stored_body.lower()

        response_headers = dict(resp.headers)
        response_cookies = resp.headers.get_list("set-cookie")

        fields.update(
            {
                "status_code": resp.status_code,
                "response_headers": response_headers,
                "response_cookies": response_cookies,
                "response_body": stored_body,
                "response_body_truncated": truncated,
                "response_size_bytes": len(resp.content),
                "timing_ms": round(elapsed_ms, 1),
                "technologies": detect_technologies(resp.headers, body_lower),
                "interesting_indicators": _summarize_indicators(
                    url, resp.status_code, headers, response_headers, response_cookies, stored_body
                ),
            }
        )
    except Exception as exc:
        fields["timing_ms"] = round((time.perf_counter() - start) * 1000, 1)
        # httpx's own exceptions (ConnectTimeout, ReadTimeout, ...) frequently
        # stringify to "" - never store a blank error, or the UI ends up
        # showing a bare "FAILED" with no explanation at all.
        fields["error"] = str(exc) or f"{type(exc).__name__}: the request did not complete (see timing above)."

    return fields
