"""
Vajra Parameter Intelligence (Section 21) - pure classification.

Like `recon/priority.py` and `api_mapper/categorize.py`: no I/O, every
verdict is a transparent rule, and NONE of them is a vulnerability claim.
Section 21 is explicit - "Do not classify the parameter itself as
vulnerable." A classification here says what *shape* a parameter has and
which review areas that shape tends to touch; confirming anything needs
authorized requests and evidence.
"""
from __future__ import annotations

import re

_NUMERIC_RE = re.compile(r"^-?\d+$")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_BOOLEAN_TOKENS = {"true", "false", "0", "1", "yes", "no"}

# An identifier-ish name: `id`, `user_id`, `orderId`, `uuid`, `...-ref`, `objectKey`.
_ID_NAME_RE = re.compile(r"(^|[_\-])(id|ids|uid|guid|uuid|ref|key)$|^id[_\-]|Id$", re.IGNORECASE)

# Mirrors evidence/masking.py's sensitive-key regex so "this looks like a
# credential" means the same thing across the app.
_SECRET_NAME_RE = re.compile(
    r"(password|pwd|passwd|secret|token|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"client[_-]?secret|session|sid|otp|passcode|auth)",
    re.IGNORECASE,
)

CLASSIFICATIONS = (
    "Numeric object identifier",
    "UUID object identifier",
    "Opaque identifier",
    "Authentication or session credential",
    "Pagination or range control",
    "Sorting, filtering or search control",
    "Redirect or URL value",
    "File or path value",
    "Boolean flag",
    "Free-form value",
)

# Section 21 "Potential areas". Deliberately phrased as *where to look*, not
# *what is wrong*.
_REVIEW_AREAS: dict[str, list[str]] = {
    "Numeric object identifier": [
        "Object-level authorization (BOLA / IDOR)",
        "Object ownership between controlled accounts",
        "Resource enumeration",
    ],
    "UUID object identifier": [
        "Object-level authorization (BOLA / IDOR)",
        "Object ownership between controlled accounts",
    ],
    "Opaque identifier": [
        "Object-level authorization (BOLA / IDOR)",
        "Object ownership between controlled accounts",
    ],
    "Authentication or session credential": [
        "Authentication strength and session handling",
        "Credential exposure in logs, referrers or history",
    ],
    "Pagination or range control": [
        "Resource enumeration",
        "Excessive data exposure at large page sizes",
    ],
    "Sorting, filtering or search control": [
        "Injection surface (SQL / NoSQL / ORM)",
        "Excessive data exposure via unexpected fields",
    ],
    "Redirect or URL value": [
        "Open redirect",
        "Server-side request forgery (SSRF)",
    ],
    "File or path value": [
        "Path traversal",
        "Access control on stored files",
    ],
    "Boolean flag": [
        "Privilege or feature toggling",
        "Mass assignment",
    ],
    "Free-form value": [
        "Input validation",
        "Injection surface",
    ],
}

_PAGINATION_NAMES = {
    "page", "per_page", "perpage", "page_size", "pagesize", "limit", "offset",
    "cursor", "size", "start", "count", "take", "skip", "from", "to", "range",
}
_SORT_FILTER_NAMES = {
    "sort", "sort_by", "sortby", "order", "order_by", "orderby", "dir", "direction",
    "filter", "q", "query", "search", "keyword", "term", "fields", "field",
    "expand", "include", "embed", "where", "status", "type", "category",
}
_REDIRECT_NAMES = {
    "redirect", "redirect_uri", "redirect_url", "redirecturl", "return", "return_url",
    "returnurl", "returnto", "return_to", "next", "url", "callback", "continue",
    "dest", "destination", "goto", "target", "forward",
}
_FILE_NAMES = {
    "file", "filename", "file_name", "filepath", "file_path", "path", "dir",
    "directory", "folder", "document", "doc", "attachment", "download", "upload",
    "name", "template", "page_path",
}


def value_shapes(sample_values: list[str]) -> list[str]:
    """Leak-proof summary of observed values: their *shape*, never the value."""
    shapes: list[str] = []
    values = [v for v in sample_values if v]
    if not values:
        return shapes
    if any(_UUID_RE.match(v) for v in values):
        shapes.append("uuid")
    if any(_NUMERIC_RE.match(v) for v in values):
        shapes.append("numeric")
    if all(v.lower() in _BOOLEAN_TOKENS for v in values):
        shapes.append("boolean-like")
    if not shapes:
        shapes.append("free text")
    return shapes


def looks_like_secret(name: str) -> bool:
    return bool(_SECRET_NAME_RE.search(name))


def classify_parameter(
    name: str, schema_types: list[str], sample_values: list[str]
) -> str:
    lname = name.lower()
    types = {t.lower() for t in schema_types if t}
    values = [v for v in sample_values if v]
    has_numeric = any(_NUMERIC_RE.match(v) for v in values)
    has_uuid = any(_UUID_RE.match(v) for v in values)
    numeric_type = bool(types & {"integer", "number", "int", "long", "float", "double"})
    boolean_type = bool(types & {"boolean", "bool"})

    if looks_like_secret(name):
        return "Authentication or session credential"
    if lname in _REDIRECT_NAMES:
        return "Redirect or URL value"
    if lname in _FILE_NAMES:
        return "File or path value"
    if lname in _PAGINATION_NAMES:
        return "Pagination or range control"
    if lname in _SORT_FILTER_NAMES:
        return "Sorting, filtering or search control"

    if _ID_NAME_RE.search(name) or lname in {"id", "pid", "oid", "gid"}:
        if has_uuid or "uuid" in types:
            return "UUID object identifier"
        if has_numeric or numeric_type:
            return "Numeric object identifier"
        return "Opaque identifier"

    # No id-ish name, but the values themselves are unambiguous identifiers.
    if values and all(_UUID_RE.match(v) for v in values):
        return "UUID object identifier"

    if boolean_type or (values and all(v.lower() in _BOOLEAN_TOKENS for v in values)):
        return "Boolean flag"
    if lname.startswith(("is_", "has_", "allow_", "enable", "disable", "show_", "with_")):
        return "Boolean flag"

    return "Free-form value"


def review_areas(classification: str) -> list[str]:
    return list(_REVIEW_AREAS.get(classification, _REVIEW_AREAS["Free-form value"]))


# Identifier and credential parameters surface first - they carry the
# access-control questions Section 21 cares about most.
_SORT_RANK: dict[str, int] = {
    "Numeric object identifier": 0,
    "UUID object identifier": 0,
    "Opaque identifier": 1,
    "Authentication or session credential": 1,
    "Redirect or URL value": 2,
    "File or path value": 2,
}


def sort_rank(classification: str) -> int:
    return _SORT_RANK.get(classification, 5)
