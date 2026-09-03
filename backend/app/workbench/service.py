"""
Vajra Access Control Workbench (Section 17) - a computed planning view.

Vajra Diff and Access-Control Scenarios already compare captured requests.
The gap Section 17 names is the *setup*: pick session A, session B, an
endpoint, an object identifier, then walk the comparison. This service
looks at the project's real captures and tells the hunter, per endpoint
shape, whether a comparison is ready to run or what to capture next - and
which existing pairs to open in Diff.

Computed on read, never sends a request.
"""
from __future__ import annotations

import hashlib
from itertools import combinations
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.api_mapper.categorize import normalize_path
from app.diff.service import _identity_marker
from app.http.models import HttpTransaction
from app.identities.models import IdentityProfile
from app.workbench.teaching import TEST_TYPES

_MAX_SUGGESTED_PAIRS = 6
_MAX_CAPTURES_LISTED = 12


def _identity_fingerprint(tx: HttpTransaction) -> str:
    if tx.identity_profile_key:
        return f"profile:{tx.identity_profile_key}"
    return "manual:" + hashlib.sha256(_identity_marker(tx.request_headers).encode("utf-8")).hexdigest()[:16]


def _object_tokens(path: str) -> list[str]:
    original = [seg for seg in path.split("/") if seg]
    normalized = [seg for seg in normalize_path(path).split("/") if seg]
    return [orig for orig, norm in zip(original, normalized) if norm == "{id}"]


def build_workbench(db: Session, project_id: int) -> dict:
    profiles = (
        db.query(IdentityProfile)
        .filter(IdentityProfile.project_id == project_id)
        .order_by(IdentityProfile.name)
        .all()
    )
    enabled_profiles = [p for p in profiles if p.enabled]

    transactions = (
        db.query(HttpTransaction)
        .filter(HttpTransaction.project_id == project_id)
        .order_by(HttpTransaction.created_at)
        .all()
    )

    groups: dict[str, dict] = {}
    for tx in transactions:
        pattern = normalize_path(urlsplit(tx.url).path or "/")
        group = groups.setdefault(
            pattern,
            {"pattern": pattern, "methods": set(), "captures": [], "object_tokens": set()},
        )
        group["methods"].add(tx.method)
        group["object_tokens"].update(_object_tokens(urlsplit(tx.url).path or "/"))
        group["captures"].append(
            {
                "transaction_id": tx.id,
                "method": tx.method,
                "url": tx.url,
                "identity_name": tx.identity_profile_name or "Manual / unnamed credentials",
                "identity_profile_id": tx.identity_profile_id,
                "controlled_identity": bool(tx.identity_profile_key),
                "status_code": tx.status_code,
                "error": bool(tx.error),
                "_fingerprint": _identity_fingerprint(tx),
            }
        )

    endpoint_groups = []
    for pattern, group in sorted(groups.items()):
        captures = group["captures"]
        usable = [c for c in captures if not c["error"]]
        identities = {c["_fingerprint"] for c in usable}
        has_object_id = "{id}" in pattern

        suggested_pairs = []
        for a, b in combinations(usable, 2):
            if a["_fingerprint"] != b["_fingerprint"] and a["method"] == b["method"]:
                suggested_pairs.append(
                    {
                        "transaction_a_id": a["transaction_id"],
                        "transaction_b_id": b["transaction_id"],
                        "identity_a": a["identity_name"],
                        "identity_b": b["identity_name"],
                    }
                )
            if len(suggested_pairs) >= _MAX_SUGGESTED_PAIRS:
                break

        if not usable:
            readiness = "no_usable_captures"
            next_step = "Every capture against this shape failed before a response. Re-send it."
        elif len(identities) >= 2:
            readiness = "ready"
            next_step = "Open Diff on a suggested pair below and confirm the returned data's owner."
            if has_object_id and len(group["object_tokens"]) < 2:
                next_step = (
                    "You have two identities but every capture used the same object identifier. For a "
                    "horizontal test, have one identity request an object owned by the other, then open Diff."
                )
        elif len(usable) >= 1:
            readiness = "needs_second_identity"
            only = next(iter(usable))["identity_name"]
            next_step = (
                f"Captured only as '{only}'. Re-send the same request selecting a second controlled "
                "identity, then this shape becomes comparable."
            )
        else:  # pragma: no cover - covered by the not-usable branch above
            readiness = "single_capture"
            next_step = "Capture this shape at least twice, with two different controlled identities."

        endpoint_groups.append(
            {
                "pattern": pattern,
                "methods": sorted(group["methods"]),
                "has_object_identifier": has_object_id,
                "distinct_identities": len(identities),
                "distinct_object_identifiers": len(group["object_tokens"]),
                "capture_count": len(captures),
                "captures": [
                    {k: v for k, v in c.items() if not k.startswith("_")}
                    for c in captures[:_MAX_CAPTURES_LISTED]
                ],
                "suggested_pairs": suggested_pairs,
                "readiness": readiness,
                "next_step": next_step,
            }
        )

    # Endpoints most ready to test first.
    _ORDER = {"ready": 0, "needs_second_identity": 1, "no_usable_captures": 2, "single_capture": 3}
    endpoint_groups.sort(key=lambda g: (_ORDER.get(g["readiness"], 9), -g["distinct_identities"], g["pattern"]))

    setup_warnings: list[str] = []
    if len(enabled_profiles) < 2:
        setup_warnings.append(
            "Define at least two controlled identities (HTTP Inspector -> Manage controlled identities). "
            "Every access-control test compares two different accounts you are authorized to use."
        )
    if not endpoint_groups:
        setup_warnings.append(
            "No requests captured yet. Send an authenticated request through the HTTP Inspector to begin."
        )

    return {
        "test_types": [
            {
                "key": t.key,
                "name": t.name,
                "definition": t.definition,
                "how_to_set_up": list(t.how_to_set_up),
                "signals_worth_a_finding": list(t.signals_worth_a_finding),
                "evidence_needed": list(t.evidence_needed),
            }
            for t in TEST_TYPES
        ],
        "identities": [
            {"id": p.id, "name": p.name, "enabled": p.enabled} for p in profiles
        ],
        "endpoint_groups": endpoint_groups,
        "ready_endpoint_count": sum(1 for g in endpoint_groups if g["readiness"] == "ready"),
        "setup_warnings": setup_warnings,
        "note": (
            "Vajra never sends these comparisons for you. Capture each request yourself with a controlled "
            "account in an authorized environment, then compare in Diff. A high Diff score is a triage "
            "signal that still needs manual ownership confirmation and program-policy review."
        ),
    }
