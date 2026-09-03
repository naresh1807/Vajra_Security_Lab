"""
Vajra API Mapper (Section 14) - a computed view over three sources of real,
already-collected data:

  1. Vajra HTTP Inspector's transaction history (real requests you sent).
  2. Vajra JS Inspector's API_ROUTE findings (paths extracted from JS).
  3. ScopeGuard-approved endpoints retained by metadata/crawl discovery.

Computing the grouped map on read keeps it honest: it cannot drift out of sync
with the source records it represents.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlsplit

from sqlalchemy.orm import Session

from app.api_mapper.categorize import categorize_path, has_object_identifier, normalize_path, score_endpoint, suggested_investigation
from app.http.models import HttpTransaction
from app.js_inspector.models import FindingType, JsFile, JsFinding
from app.surface.models import DiscoveredEndpoint


def build_api_map(db: Session, project_id: int) -> dict[str, list[dict]]:
    endpoints: dict[str, dict] = {}

    def _entry_for(normalized: str) -> dict:
        return endpoints.setdefault(
            normalized,
            {
                "pattern": normalized, "methods": set(), "sample_urls": set(), "sources": set(),
                "seen_json": False, "query_parameters": set(), "tags": set(),
                "security_schemes": set(), "deprecated_methods": set(), "operation_summaries": set(),
            },
        )

    transactions = db.query(HttpTransaction).filter(HttpTransaction.project_id == project_id).all()
    for tx in transactions:
        parts = urlsplit(tx.url)
        path = parts.path or "/"
        entry = _entry_for(normalize_path(path))
        entry["methods"].add(tx.method)
        entry["sample_urls"].add(tx.url)
        entry["sources"].add("http")
        entry["query_parameters"].update(key for key, _ in parse_qsl(parts.query, keep_blank_values=True))
        content_type = next((v for k, v in tx.response_headers.items() if k.lower() == "content-type"), "")
        if "json" in content_type.lower():
            entry["seen_json"] = True

    js_findings = (
        db.query(JsFinding)
        .join(JsFile, JsFinding.js_file_id == JsFile.id)
        .filter(JsFile.project_id == project_id, JsFinding.finding_type == FindingType.API_ROUTE)
        .all()
    )
    for finding in js_findings:
        entry = _entry_for(normalize_path(finding.value))
        entry["sources"].add("js")

    crawled = db.query(DiscoveredEndpoint).filter(DiscoveredEndpoint.project_id == project_id).all()
    for item in crawled:
        entry = _entry_for(normalize_path(item.path))
        entry["methods"].add(item.method)
        entry["sample_urls"].add(item.url)
        entry["sources"].add(item.source)
        entry["query_parameters"].update(item.query_parameters)
        entry["tags"].update(item.tags or [])
        entry["security_schemes"].update(
            scheme for requirement in (item.security_requirements or []) for scheme in requirement
        )
        if item.deprecated:
            entry["deprecated_methods"].add(item.method)
        if item.summary:
            entry["operation_summaries"].add(f"{item.method}: {item.summary}")
        if item.content_type and "json" in item.content_type.lower():
            entry["seen_json"] = True

    grouped: dict[str, list[dict]] = {}
    for normalized, entry in endpoints.items():
        category = categorize_path(normalized)
        score, reasons = score_endpoint(normalized, category, entry["seen_json"])
        if entry["query_parameters"]:
            score = min(100, score + 10)
            reasons.append(f"Observed query parameters: {', '.join(sorted(entry['query_parameters']))}.")
        if entry["security_schemes"]:
            score = min(100, score + 5)
            reasons.append(f"Specification declares authentication: {', '.join(sorted(entry['security_schemes']))}.")
        record = {
            "pattern": normalized,
            "category": category,
            "methods": sorted(entry["methods"]),
            "sample_urls": sorted(entry["sample_urls"])[:5],
            "sources": sorted(entry["sources"]),
            "query_parameters": sorted(entry["query_parameters"]),
            "tags": sorted(entry["tags"]),
            "security_schemes": sorted(entry["security_schemes"]),
            "deprecated_methods": sorted(entry["deprecated_methods"]),
            "operation_summaries": sorted(entry["operation_summaries"])[:10],
            "has_object_identifier": has_object_identifier(normalized),
            "interesting_score": score,
            "reasons": reasons,
            "suggested_investigation": suggested_investigation(normalized, category),
        }
        grouped.setdefault(category, []).append(record)

    for records in grouped.values():
        records.sort(key=lambda r: r["interesting_score"], reverse=True)

    return grouped
