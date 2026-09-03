"""
Vajra Authentication Flow Analyzer (Section 18) - a computed map.

Takes every request path Vajra has already seen for a project (HTTP
Inspector history, discovered endpoints, JS routes, public metadata),
assigns each to a canonical auth-flow stage, and returns the flow with
per-stage manual-review checks and a short "where to focus" list.

It never sends a request. Section 18: "Do not automatically attack
accounts." Every stage is a prompt for the hunter to walk manually with
their own controlled test account.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.api_mapper.categorize import normalize_path
from app.authflow.stages import FLOW_ORDER, STAGE_BY_KEY, assign_stage
from app.http.models import HttpTransaction
from app.js_inspector.models import FindingType, JsFile, JsFinding
from app.surface.models import DiscoveredEndpoint, PublicMetadataDocument

_MAX_ENDPOINTS_PER_STAGE = 20


class _StageAcc:
    __slots__ = ("endpoints",)

    def __init__(self) -> None:
        # keyed by (method, normalized_path) -> {"sources": set, "sample_url": str | None}
        self.endpoints: dict[tuple[str, str], dict] = {}

    def add(self, method: str, path: str, source: str, sample_url: str | None) -> None:
        key = (method.upper(), normalize_path(path or "/"))
        slot = self.endpoints.setdefault(key, {"sources": set(), "sample_url": None})
        slot["sources"].add(source)
        if sample_url and not slot["sample_url"]:
            slot["sample_url"] = sample_url


def _path_of(value: str) -> str:
    return urlsplit(value.strip()).path or value.strip() or "/"


def build_auth_flow(db: Session, project_id: int) -> dict:
    accs: dict[str, _StageAcc] = {key: _StageAcc() for key in FLOW_ORDER}

    def _route(method: str, raw_path_or_url: str, source: str, sample_url: str | None) -> None:
        path = _path_of(raw_path_or_url)
        stage = assign_stage(method, path)
        if stage is not None:
            accs[stage].add(method, path, source, sample_url)

    for tx in db.query(HttpTransaction).filter(HttpTransaction.project_id == project_id):
        _route(tx.method, tx.url, "http", tx.url)

    for endpoint in db.query(DiscoveredEndpoint).filter(DiscoveredEndpoint.project_id == project_id):
        _route(endpoint.method, endpoint.path, endpoint.source or "spec", endpoint.url)

    js_routes = (
        db.query(JsFinding)
        .join(JsFile, JsFinding.js_file_id == JsFile.id)
        .filter(JsFile.project_id == project_id, JsFinding.finding_type == FindingType.API_ROUTE)
    )
    for finding in js_routes:
        absolute = finding.value if finding.value.lower().startswith(("http://", "https://")) else None
        _route("GET", finding.value, "js", absolute)

    metadata_docs = db.query(PublicMetadataDocument).filter(
        PublicMetadataDocument.project_id == project_id,
        PublicMetadataDocument.error.is_(None),
    )
    for document in metadata_docs:
        for entry in document.entries or []:
            if entry.get("type") in {"allow", "disallow", "url", "operation"} and entry.get("value"):
                _route("GET", entry["value"], "metadata", None)

    stages_out: list[dict] = []
    observed_keys: set[str] = set()
    for key in FLOW_ORDER:
        spec = STAGE_BY_KEY[key]
        acc = accs[key]
        endpoints = [
            {
                "method": method,
                "path": path,
                "sources": sorted(slot["sources"]),
                "sample_url": slot["sample_url"],
            }
            for (method, path), slot in sorted(acc.endpoints.items())
        ][:_MAX_ENDPOINTS_PER_STAGE]
        if endpoints:
            observed_keys.add(key)
        stages_out.append(
            {
                "key": spec.key,
                "title": spec.title,
                "why": spec.why,
                "review_checks": list(spec.review_checks),
                "observed": bool(endpoints),
                "endpoints": endpoints,
            }
        )

    return {
        "stages": stages_out,
        "observed_stage_count": len(observed_keys),
        "total_stage_count": len(FLOW_ORDER),
        "review_focus": _review_focus(observed_keys),
        "note": (
            "Vajra maps this flow from paths it has already seen - it never exercises these "
            "endpoints. Walk each stage manually with your own controlled test account, within "
            "program rules."
        ),
    }


def _review_focus(observed: set[str]) -> list[str]:
    focus: list[str] = []
    if "password_reset" in observed:
        focus.append(
            "A password-reset flow is exposed - verify token unpredictability, single-use and expiry, "
            "host-header influence on the reset link, and session invalidation after reset."
        )
    if "mfa" in observed:
        focus.append(
            "MFA endpoints are present - look for a login or token path that completes without the second factor."
        )
    if "registration" in observed and "email_verification" not in observed:
        focus.append(
            "Registration was observed but no verification step - check whether an unverified account can act."
        )
    if "login" in observed and "logout" not in observed:
        focus.append(
            "Login was observed but no logout / termination endpoint - confirm how sessions end and whether "
            "issued tokens can be revoked."
        )
    if "session_issuance" in observed:
        focus.append(
            "Token issuance is exposed - review token lifetime and claims, refresh-token rotation, and how the "
            "token is delivered and stored."
        )
    if "account_management" in observed:
        focus.append(
            "Account-management endpoints are present - treat email change as a credential change (re-auth + "
            "verify new address) and check every id-bearing endpoint for cross-user access."
        )
    if not observed:
        focus.append(
            "No auth-flow endpoints matched yet. Send login / account requests through the HTTP Inspector, or "
            "discover endpoints from a spec, and they will map here."
        )
    return focus
