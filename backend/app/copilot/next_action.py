"""
Vajra Next-Best-Action Engine (Section 26).

"After each stage, Vajra recommends the next useful action ... The beginner
never gets lost." This reads the project's real state - what's been
discovered, sent, compared, investigated - and picks the single most
useful next move, plus the shortcut to get there. Deterministic, no I/O
beyond the queries here, never a vulnerability claim.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api_mapper.categorize import has_object_identifier, normalize_path
from app.authflow.stages import assign_stage
from app.diff.models import AccessControlScenario
from app.http.models import HttpTransaction
from app.investigations.models import Investigation, InvestigationSource, InvestigationStatus
from app.js_inspector.models import FindingType, JsFile, JsFinding
from app.recon.models import Asset
from app.recon.priority import HIGH_PRIORITY_THRESHOLD
from app.reports.models import Report
from app.surface.models import DiscoveredEndpoint

_AUTH_KEYWORDS = ("login", "auth", "session", "password", "mfa", "2fa", "oauth", "token", "register", "sso")


def compute_next_best_action(db: Session, project_id: int) -> dict:
    assets = (
        db.query(Asset)
        .filter(Asset.project_id == project_id)
        .order_by(Asset.priority_score.desc())
        .all()
    )
    unreviewed_high = [a for a in assets if not a.reviewed and a.priority_score >= HIGH_PRIORITY_THRESHOLD]

    endpoints = db.query(DiscoveredEndpoint).filter(DiscoveredEndpoint.project_id == project_id).all()
    object_id_patterns = sorted(
        {normalize_path(e.path) for e in endpoints if has_object_identifier(normalize_path(e.path))}
    )

    transactions = db.query(HttpTransaction).filter(HttpTransaction.project_id == project_id).all()
    js_file_count = db.query(func.count(JsFile.id)).filter(JsFile.project_id == project_id).scalar() or 0
    js_route_count = (
        db.query(func.count(JsFinding.id))
        .join(JsFile, JsFinding.js_file_id == JsFile.id)
        .filter(JsFile.project_id == project_id, JsFinding.finding_type == FindingType.API_ROUTE)
        .scalar()
    ) or 0
    scenario_count = (
        db.query(func.count(AccessControlScenario.id))
        .filter(AccessControlScenario.project_id == project_id)
        .scalar()
    ) or 0

    auth_stages: set[str] = set()
    for tx in transactions:
        stage = assign_stage(tx.method, urlsplit(tx.url).path or "/")
        if stage:
            auth_stages.add(stage)
    for e in endpoints:
        stage = assign_stage(e.method, e.path)
        if stage:
            auth_stages.add(stage)

    investigations = db.query(Investigation).filter(Investigation.project_id == project_id).all()
    open_investigations = [i for i in investigations if i.status == InvestigationStatus.OPEN]
    validated = [i for i in investigations if i.status == InvestigationStatus.VALIDATED]
    has_access_control_investigation = any(
        i.source == InvestigationSource.DIFF_RESULT or len(i.linked_transaction_ids or []) >= 2
        for i in investigations
    )
    has_auth_investigation = any(
        any(k in " ".join([i.title or "", i.endpoint or "", i.notes or "", i.ai_notes or ""]).lower() for k in _AUTH_KEYWORDS)
        for i in investigations
    )
    report_ids = {r.investigation_id for r in db.query(Report.investigation_id).join(
        Investigation, Report.investigation_id == Investigation.id
    ).filter(Investigation.project_id == project_id)}

    # The "N areas found" list from Section 26's example.
    focus_areas: list[dict] = []
    if any(a.priority_category in ("auth", "account", "admin") for a in unreviewed_high) or "login" in auth_stages:
        focus_areas.append({"label": "Authentication surface", "detail": "Login / session / recovery endpoints are in scope.", "route": "auth-flow"})
    if object_id_patterns:
        focus_areas.append({
            "label": "API endpoints with object identifiers",
            "detail": f"{len(object_id_patterns)} endpoint shape(s) take an object id, e.g. {object_id_patterns[0]}.",
            "route": "access-control",
        })
    if js_route_count:
        focus_areas.append({"label": "Routes extracted from JavaScript", "detail": f"{js_route_count} route(s) found in analyzed JS.", "route": "api-map"})
    if auth_stages:
        focus_areas.append({"label": "Mapped authentication flow", "detail": f"{len(auth_stages)} auth-flow stage(s) observed.", "route": "auth-flow"})

    def result(headline, reason, *, route=None, cta=None, asset=None):
        return {
            "headline": headline,
            "reason": reason,
            "cta_label": cta,
            "cta_route": route,
            "focus_areas": focus_areas,
            "recommended_asset_id": asset.id if asset else None,
            "recommended_hostname": asset.hostname if asset else None,
            "alternatives": [
                f"{a.hostname} ({a.priority_category or 'general'}, score {a.priority_score})"
                for a in [x for x in assets if not x.reviewed][1:4]
            ],
        }

    if not assets:
        return result(
            "Run recon to discover the attack surface",
            "No assets yet. Start recon - Vajra will find subdomains (passively), check each against ScopeGuard, "
            "resolve DNS, probe live hosts, and prioritize what it finds.",
        )

    if unreviewed_high and not investigations:
        top = unreviewed_high[0]
        return result(
            f"Investigate {top.hostname}",
            f"{len(unreviewed_high)} high-priority asset(s) are waiting. '{top.hostname}' scored highest "
            f"({top.priority_score}/100)"
            + (f" - {', '.join(top.priority_reasons)}." if top.priority_reasons else ".")
            + " Open it in the HTTP Inspector, then start an investigation from the Copilot panel.",
            asset=top,
        )

    if object_id_patterns and scenario_count == 0 and not has_access_control_investigation:
        return result(
            "Test object-level access control",
            f"{len(object_id_patterns)} discovered endpoint shape(s) take an object identifier "
            f"(e.g. {object_id_patterns[0]}) but no access-control comparison has been set up. The Workbench "
            "walks you through capturing the same request as two controlled identities.",
            route="access-control",
            cta="Open the Access Control Workbench",
        )

    if auth_stages and not has_auth_investigation:
        return result(
            "Review the authentication flow",
            f"{len(auth_stages)} auth-flow stage(s) were mapped from discovered paths, and none has been "
            "investigated yet. The Auth Flow Analyzer lists the manual-review checks for each.",
            route="auth-flow",
            cta="Open the Auth Flow Analyzer",
        )

    if not transactions and not investigations and (endpoints or assets):
        return result(
            "Send a request through the HTTP Inspector",
            "You have attack surface but no captured requests yet. Send an authenticated request to an "
            "in-scope endpoint - that unlocks the Analyzer, Diff, and access-control testing.",
            route="http",
            cta="Open the HTTP Inspector",
        )

    open_without_report = [i for i in open_investigations if i.id not in report_ids]
    if open_without_report:
        target = open_without_report[0]
        return result(
            f"Take '{target.title}' toward validation",
            f"{len(open_investigations)} investigation(s) are open. Work the false-positive checklist, attach "
            "evidence, and fill in observed vs. potential impact before marking it validated.",
            route=f"investigations/{target.id}",
            cta="Open the investigation",
        )

    validated_without_report = [i for i in validated if i.id not in report_ids]
    if validated_without_report:
        target = validated_without_report[0]
        return result(
            f"Generate the report for '{target.title}'",
            "You have a validated finding with no report yet. Vajra will auto-draft it from your recorded "
            "evidence and notes, with a readiness score.",
            route=f"investigations/{target.id}/report",
            cta="Open the Report Generator",
        )

    if js_file_count == 0:
        return result(
            "Analyze a JavaScript file",
            "No JS analyzed yet. The JS Inspector extracts API routes, GraphQL/WebSocket URLs, and masked "
            "potential secrets - often the fastest way to find undocumented endpoints.",
            route="js",
            cta="Open the JS Inspector",
        )

    return result(
        "Keep working the attack surface",
        "The obvious next steps are done. Widen coverage: analyze more JS, send more requests, or revisit "
        "unreviewed assets in the Attack Surface table.",
        route="parameters",
        cta="Review Parameter Intelligence",
    )
