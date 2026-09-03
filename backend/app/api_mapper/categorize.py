"""
Vajra API Priority Engine / Endpoint Intelligence (Sections 15, 20).

Pure, transparent functions - no I/O - so they're trivial to unit test and
so every score comes with a stated reason, matching the rest of this
codebase's "never a black-box number" rule (see recon/priority.py).
"""
from __future__ import annotations

import re

_NUMERIC_RE = re.compile(r"^\d+$")
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_PLACEHOLDER_RE = re.compile(r"^\{.+\}$")
_PARAM_RE = re.compile(r"^:\w+$")

_CATEGORY_SIGNALS: list[tuple[tuple[str, ...], str]] = [
    (("login", "logout", "register", "auth", "password", "token", "session", "sso"), "Authentication"),
    (("graphql",), "GraphQL"),
    (("admin", "internal", "manage"), "Admin"),
    (("payment", "payments", "billing", "invoice", "checkout"), "Payments"),
    (("file", "files", "upload", "uploads", "media"), "Files"),
    (("order", "orders", "cart"), "Orders"),
    (("user", "users", "account", "accounts", "profile"), "Users"),
]


def normalize_path(path: str) -> str:
    """Collapse likely object identifiers to {id} for grouping.

    /api/orders/123        -> /api/orders/{id}
    /api/users/{id}        -> /api/users/{id}   (already a placeholder)
    /api/files/:fileId     -> /api/files/{id}
    """
    segments = path.split("/")
    normalized = []
    for seg in segments:
        if seg and (_NUMERIC_RE.match(seg) or _UUID_RE.match(seg) or _PLACEHOLDER_RE.match(seg) or _PARAM_RE.match(seg)):
            normalized.append("{id}")
        else:
            normalized.append(seg)
    return "/".join(normalized)


def has_object_identifier(normalized_path: str) -> bool:
    return "{id}" in normalized_path


def categorize_path(path: str) -> str:
    lower = path.lower()
    for keywords, category in _CATEGORY_SIGNALS:
        if any(kw in lower for kw in keywords):
            return category
    return "Other"


def score_endpoint(normalized_path: str, category: str, seen_json: bool) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    if has_object_identifier(normalized_path):
        score += 40
        reasons.append("Endpoint contains an object identifier.")

    if category in ("Authentication", "Admin", "Payments", "GraphQL"):
        score += 25
        reasons.append(f"Path suggests {category.lower()} functionality.")
    elif category in ("Users", "Orders", "Files"):
        score += 15
        reasons.append(f"Path suggests {category.lower()}-related resource access.")

    if seen_json:
        score += 15
        reasons.append("Observed a JSON response from this endpoint.")

    if not reasons:
        reasons.append("No strong signals yet - inspect it to learn more.")

    return min(score, 100), reasons


def suggested_investigation(normalized_path: str, category: str) -> str:
    if has_object_identifier(normalized_path):
        return (
            "Potential Category: Object Authorization. Compare authorized requests involving objects owned by "
            "controlled test accounts where program rules permit."
        )
    if category == "Authentication":
        return "Review the flow this endpoint belongs to (registration, login, password reset, session issuance)."
    if category == "Admin":
        return "Confirm this requires a privileged session, and note exactly what a low-privilege session can reach."
    return "Send a request through the HTTP Inspector to see its live behavior."
