"""
Vajra JS Inspector (Section 19) orchestration: fetch a JS file - through the
same ScopeGuard check and rate limiter as every other outbound request in
this codebase (Section 5) - then run the regex extractors and persist the
findings.
"""
from __future__ import annotations

import asyncio

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.outbound import request_with_safe_redirects
from app.js_inspector.extraction import (
    extract_api_routes,
    extract_config_references,
    extract_graphql_urls,
    extract_potential_secrets,
    extract_source_maps,
    extract_websocket_urls,
)
from app.js_inspector.models import FindingType, JsFile, JsFinding
from app.projects.models import Project
from app.scopeguard.engine import check_scope, rate_limiter
from app.scopeguard.models import ScopeAuditLog, ScopeDecision

MAX_ANALYZED_CHARS = 2_000_000


class ScopeBlockedError(Exception):
    def __init__(self, reason: str, decision: ScopeDecision):
        super().__init__(reason)
        self.reason = reason
        self.decision = decision


async def fetch_and_analyze_js(db: Session, project: Project, url: str) -> JsFile:
    host = url.split("//", 1)[-1].split("/", 1)[0].split(":")[0]
    result = check_scope(project, host)

    db.add(
        ScopeAuditLog(
            project_id=project.id,
            target_input=url,
            normalized_target=result.normalized_target,
            decision=result.decision,
            reason=result.reason,
            operation="js_inspector_fetch",
        )
    )
    db.commit()

    if result.decision != ScopeDecision.ALLOWED:
        raise ScopeBlockedError(result.reason, result.decision)

    while not rate_limiter.allow(project.id, project.rate_limit_rps):
        await asyncio.sleep(1.0 / max(project.rate_limit_rps, 0.1))

    js_file = JsFile(project_id=project.id, url=url)

    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_seconds, headers={"User-Agent": settings.http_user_agent}, follow_redirects=False
        ) as client:
            resp = await request_with_safe_redirects(client, project, "GET", url)
        js_file.status_code = resp.status_code
        js_file.size_bytes = len(resp.content)
        text = (resp.text or "")[:MAX_ANALYZED_CHARS]
    except Exception as exc:
        js_file.error = str(exc) or f"{type(exc).__name__}: the request did not complete."
        db.add(js_file)
        db.commit()
        db.refresh(js_file)
        return js_file

    findings: list[JsFinding] = []
    for route in extract_api_routes(text):
        findings.append(JsFinding(finding_type=FindingType.API_ROUTE, value=route))
    for gql in extract_graphql_urls(text):
        findings.append(JsFinding(finding_type=FindingType.GRAPHQL_URL, value=gql))
    for ws in extract_websocket_urls(text):
        findings.append(JsFinding(finding_type=FindingType.WEBSOCKET_URL, value=ws))
    for src_map in extract_source_maps(text):
        findings.append(JsFinding(finding_type=FindingType.SOURCE_MAP, value=src_map))
    for key, value in extract_config_references(text).items():
        findings.append(JsFinding(finding_type=FindingType.CONFIG_REFERENCE, value=value, context=key))
    for secret in extract_potential_secrets(text):
        findings.append(
            JsFinding(
                finding_type=FindingType.POTENTIAL_SECRET,
                value=secret.masked_value,
                context=secret.context,
                metadata_={"label": secret.label},
            )
        )

    js_file.findings = findings
    db.add(js_file)
    db.commit()
    db.refresh(js_file)
    return js_file
