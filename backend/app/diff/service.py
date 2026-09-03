"""
Vajra Diff (Section 16) and the Access Control Workbench it powers
(Section 17) - compares two already-captured HTTP Inspector transactions
to test horizontal/vertical access control.

The entire point of this module is captured in one sentence from the
spec: Vajra should NOT say "Confirmed IDOR." It reports a confidence
score and the signals behind it, and explicitly tells the hunter when a
comparison doesn't actually test anything (e.g. both requests used the
same identity) - a wrong diff setup is a common beginner mistake, and
staying quiet about it would just produce a misleadingly low confidence
number instead of teaching why.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from app.api_mapper.categorize import normalize_path
from app.core.headers import get_header_ci
from app.diff.schemas import DiffFindingOut, DiffResultOut, HeaderDiffEntry
from app.http.models import HttpTransaction

_IGNORED_HEADERS = {"date", "etag", "content-length", "x-request-id", "cf-ray", "server-timing"}


def _identity_marker(headers: dict[str, str]) -> str:
    auth = get_header_ci(headers, "authorization") or ""
    cookie = get_header_ci(headers, "cookie") or ""
    return f"auth={auth}|cookie={cookie}"


def _identity_comparison(tx_a: HttpTransaction, tx_b: HttpTransaction) -> tuple[bool, str, str, str]:
    """Prefer stable controlled-profile attribution over comparing secrets."""
    key_a = getattr(tx_a, "identity_profile_key", None)
    key_b = getattr(tx_b, "identity_profile_key", None)
    name_a = getattr(tx_a, "identity_profile_name", None) or "Manual / unnamed credentials"
    name_b = getattr(tx_b, "identity_profile_name", None) or "Manual / unnamed credentials"
    if key_a and key_b:
        return key_a == key_b, name_a, name_b, "controlled profiles"
    return (
        _identity_marker(tx_a.request_headers) == _identity_marker(tx_b.request_headers),
        name_a,
        name_b,
        "Authorization/Cookie headers",
    )


def _extract_json_keys(body: str | None, max_depth: int = 4) -> set[str]:
    """Flattened dotted key paths, e.g. {"user": {"id": 1}} -> {"user", "user.id"}.

    Arrays are sampled (first 3 items) rather than fully walked - the
    point is structural shape, not an exhaustive diff of every list item.
    """
    if not body:
        return set()
    try:
        parsed = json.loads(body)
    except (ValueError, TypeError):
        return set()

    keys: set[str] = set()

    def walk(node: object, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                path = f"{prefix}.{k}" if prefix else str(k)
                keys.add(path)
                walk(v, path, depth + 1)
        elif isinstance(node, list):
            for item in node[:3]:
                walk(item, f"{prefix}[]", depth + 1)

    walk(parsed, "", 0)
    return keys


def _score(
    same_identity: bool,
    both_success: bool,
    status_match: bool,
    structurally_similar: bool,
    size_ratio: float,
    identity_basis: str,
) -> tuple[int, str, list[str]]:
    notes: list[str] = []
    score = 0

    if same_identity:
        notes.append(
            f"Both requests used the same identity ({identity_basis}) - this only shows the endpoint's normal "
            "behavior across two objects, not whether access control is enforced. Repeat this comparison "
            "using two different controlled accounts to actually test authorization."
        )
    else:
        score += 30
        notes.append(f"Requests used different identities ({identity_basis}) - this genuinely tests access control.")

    if both_success:
        score += 25
        notes.append("Both requests returned a successful (2xx) status code.")
    elif status_match:
        notes.append("Both requests returned the same non-success status - no access difference observed here.")
    else:
        notes.append("Requests returned different status codes - this may already show access control working as expected, or a different failure reason worth checking.")

    if structurally_similar:
        score += 25
        notes.append("Response bodies share a similar JSON structure - both likely came from the same code path.")

    if size_ratio >= 0.8:
        score += 20
        notes.append(f"Response sizes are comparable (ratio {size_ratio:.2f}) - both look like real, non-empty payloads.")

    score = min(score, 100)

    if same_identity:
        category = "Inconclusive - same identity used"
    elif score >= 60:
        category = "Potential Broken Object Authorization"
    elif score >= 30:
        category = "Worth a closer look"
    else:
        category = "Low signal"

    return score, category, notes


def compare_transactions(tx_a: HttpTransaction, tx_b: HttpTransaction) -> DiffResultOut:
    path_a = normalize_path(urlsplit(tx_a.url).path or "/")
    path_b = normalize_path(urlsplit(tx_b.url).path or "/")
    same_pattern = path_a == path_b
    same_identity, identity_a, identity_b, identity_basis = _identity_comparison(tx_a, tx_b)

    if tx_a.error or tx_b.error:
        return DiffResultOut(
            transaction_a_id=tx_a.id,
            transaction_b_id=tx_b.id,
            url_a=tx_a.url,
            url_b=tx_b.url,
            normalized_pattern=path_a if same_pattern else None,
            same_endpoint_pattern=same_pattern,
            same_identity=same_identity,
            identity_a=identity_a,
            identity_b=identity_b,
            identity_basis=identity_basis,
            status_a=tx_a.status_code,
            status_b=tx_b.status_code,
            status_match=tx_a.status_code == tx_b.status_code,
            length_a=tx_a.response_size_bytes,
            length_b=tx_b.response_size_bytes,
            header_differences=[],
            body_keys_only_in_a=[],
            body_keys_only_in_b=[],
            body_common_keys=[],
            finding=DiffFindingOut(
                confidence=0,
                category="Not comparable",
                notes=["One or both of the selected requests failed before a response was received - nothing to compare."],
            ),
        )

    if not same_pattern:
        return DiffResultOut(
            transaction_a_id=tx_a.id,
            transaction_b_id=tx_b.id,
            url_a=tx_a.url,
            url_b=tx_b.url,
            normalized_pattern=None,
            same_endpoint_pattern=False,
            same_identity=same_identity,
            identity_a=identity_a,
            identity_b=identity_b,
            identity_basis=identity_basis,
            status_a=tx_a.status_code,
            status_b=tx_b.status_code,
            status_match=tx_a.status_code == tx_b.status_code,
            length_a=tx_a.response_size_bytes,
            length_b=tx_b.response_size_bytes,
            header_differences=[],
            body_keys_only_in_a=[],
            body_keys_only_in_b=[],
            body_common_keys=[],
            finding=DiffFindingOut(
                confidence=0,
                category="Not directly comparable",
                notes=[
                    "These requests hit different endpoint shapes "
                    f"('{path_a}' vs '{path_b}'). Pick two requests against the same endpoint pattern "
                    "(e.g. the same /api/orders/{id}-style path with two different IDs) to test object-level "
                    "access control."
                ],
            ),
        )

    all_header_keys = set(tx_a.response_headers) | set(tx_b.response_headers)
    header_diffs: list[HeaderDiffEntry] = []
    for h in sorted(all_header_keys):
        if h.lower() in _IGNORED_HEADERS:
            continue
        va = get_header_ci(tx_a.response_headers, h)
        vb = get_header_ci(tx_b.response_headers, h)
        if va != vb:
            header_diffs.append(HeaderDiffEntry(header=h, value_a=va, value_b=vb))

    keys_a = _extract_json_keys(tx_a.response_body)
    keys_b = _extract_json_keys(tx_b.response_body)
    only_a = sorted(keys_a - keys_b)
    only_b = sorted(keys_b - keys_a)
    common = sorted(keys_a & keys_b)
    union_size = len(keys_a | keys_b)
    structurally_similar = union_size > 0 and (len(common) / union_size) >= 0.7

    len_a = tx_a.response_size_bytes or 0
    len_b = tx_b.response_size_bytes or 0
    size_ratio = (min(len_a, len_b) / max(len_a, len_b)) if max(len_a, len_b) else 1.0

    status_match = tx_a.status_code == tx_b.status_code
    both_success = bool(tx_a.status_code and tx_b.status_code and 200 <= tx_a.status_code < 300 and 200 <= tx_b.status_code < 300)

    confidence, category, notes = _score(
        same_identity, both_success, status_match, structurally_similar, size_ratio, identity_basis
    )

    if tx_a.url == tx_b.url:
        notes.insert(0, "These are the exact same URL - to test object-level access control, compare two requests with different object IDs.")

    return DiffResultOut(
        transaction_a_id=tx_a.id,
        transaction_b_id=tx_b.id,
        url_a=tx_a.url,
        url_b=tx_b.url,
        normalized_pattern=path_a,
        same_endpoint_pattern=True,
        same_identity=same_identity,
        identity_a=identity_a,
        identity_b=identity_b,
        identity_basis=identity_basis,
        status_a=tx_a.status_code,
        status_b=tx_b.status_code,
        status_match=status_match,
        length_a=tx_a.response_size_bytes,
        length_b=tx_b.response_size_bytes,
        header_differences=header_diffs,
        body_keys_only_in_a=only_a,
        body_keys_only_in_b=only_b,
        body_common_keys=common,
        finding=DiffFindingOut(confidence=confidence, category=category, notes=notes),
    )
