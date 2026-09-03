"""
Vajra Parameter Intelligence (Section 21) - a computed view, never a table.

Aggregates every parameter Vajra has already seen for a project, from:

  1. Vajra HTTP Inspector history - query-string names and (shape-only)
     values from real requests you sent.
  2. ScopeGuard-approved endpoints from metadata / spec / crawl discovery -
     declared parameter name, location, schema type, required flag, plus
     `{name}` placeholders in the path.
  3. Vajra JS Inspector API_ROUTE findings - query names parsed from routes
     extracted from JavaScript.

Computed on read so it can never drift from the records it summarizes.
Raw values never leave this module - only their *shape* (numeric / uuid /
boolean-like / free text), and not even that for credential-shaped names.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlsplit

from sqlalchemy.orm import Session

from app.api_mapper.categorize import normalize_path
from app.js_inspector.models import FindingType, JsFile, JsFinding
from app.http.models import HttpTransaction
from app.parameters.categorize import (
    classify_parameter,
    looks_like_secret,
    review_areas,
    sort_rank,
    value_shapes,
)
from app.surface.models import DiscoveredEndpoint

_MAX_ENDPOINTS_LISTED = 25
_MAX_SAMPLE_VALUES = 8
_MAX_VALUE_LEN = 120


class _Agg:
    __slots__ = ("name", "locations", "sources", "schema_types", "required", "endpoints", "values")

    def __init__(self, name: str) -> None:
        self.name = name
        self.locations: set[str] = set()
        self.sources: set[str] = set()
        self.schema_types: set[str] = set()
        self.required = False
        self.endpoints: set[str] = set()
        self.values: set[str] = set()

    def add_value(self, value: str) -> None:
        if value and len(value) <= _MAX_VALUE_LEN and len(self.values) < _MAX_SAMPLE_VALUES:
            self.values.add(value)


def build_parameter_inventory(db: Session, project_id: int) -> list[dict]:
    params: dict[str, _Agg] = {}

    def _get(name: str) -> _Agg:
        return params.setdefault(name, _Agg(name))

    # 1. Discovered endpoints: rich declared parameters + bare query names + path placeholders.
    for endpoint in db.query(DiscoveredEndpoint).filter(DiscoveredEndpoint.project_id == project_id):
        pattern = f"{endpoint.method} {normalize_path(endpoint.path)}"
        source = endpoint.source or "spec"

        for detail in endpoint.parameter_details or []:
            name = detail.get("name")
            if not isinstance(name, str) or not name:
                continue
            agg = _get(name)
            location = detail.get("in")
            if isinstance(location, str) and location:
                agg.locations.add(location)
            if detail.get("required"):
                agg.required = True
            schema_type = detail.get("schema_type")
            if isinstance(schema_type, str) and schema_type:
                agg.schema_types.add(schema_type)
            agg.endpoints.add(pattern)
            agg.sources.add(source)

        for name in endpoint.query_parameters or []:
            if not isinstance(name, str) or not name:
                continue
            agg = _get(name)
            agg.locations.add("query")
            agg.endpoints.add(pattern)
            agg.sources.add(source)

        for segment in endpoint.path.split("/"):
            if len(segment) > 2 and segment.startswith("{") and segment.endswith("}"):
                agg = _get(segment[1:-1])
                agg.locations.add("path")
                agg.endpoints.add(pattern)
                agg.sources.add(source)

    # 2. HTTP Inspector history: real query names, plus value SHAPES for classification.
    for tx in db.query(HttpTransaction).filter(HttpTransaction.project_id == project_id):
        split = urlsplit(tx.url)
        pattern = f"{tx.method} {normalize_path(split.path or '/')}"
        for key, value in parse_qsl(split.query, keep_blank_values=True):
            if not key:
                continue
            agg = _get(key)
            agg.locations.add("query")
            agg.endpoints.add(pattern)
            agg.sources.add("http")
            if not looks_like_secret(key):
                agg.add_value(value)

    # 3. JS Inspector API_ROUTE findings: query names parsed from extracted routes.
    js_routes = (
        db.query(JsFinding)
        .join(JsFile, JsFinding.js_file_id == JsFile.id)
        .filter(JsFile.project_id == project_id, JsFinding.finding_type == FindingType.API_ROUTE)
    )
    for finding in js_routes:
        query = urlsplit(finding.value).query
        for key, _ in parse_qsl(query, keep_blank_values=True):
            if not key:
                continue
            agg = _get(key)
            agg.locations.add("query")
            agg.sources.add("js")

    inventory: list[dict] = []
    for name, agg in params.items():
        sample_values = sorted(agg.values)
        classification = classify_parameter(name, sorted(agg.schema_types), sample_values)
        secretish = looks_like_secret(name) or classification == "Authentication or session credential"
        inventory.append(
            {
                "name": name,
                "classification": classification,
                "locations": sorted(agg.locations),
                "sources": sorted(agg.sources),
                "schema_types": sorted(agg.schema_types),
                "required": agg.required,
                "observed_endpoint_count": len(agg.endpoints),
                "endpoints": sorted(agg.endpoints)[:_MAX_ENDPOINTS_LISTED],
                # Shape only - and nothing at all for credential-shaped names.
                "value_shapes": [] if secretish else value_shapes(sample_values),
                "review_areas": review_areas(classification),
                "note": (
                    "This describes the parameter's shape, not a finding. Confirm any "
                    "behavior with authorized requests using controlled test accounts."
                ),
            }
        )

    inventory.sort(
        key=lambda row: (
            sort_rank(row["classification"]),
            -row["observed_endpoint_count"],
            row["name"].lower(),
        )
    )
    return inventory
