"""
Vajra Asset Priority Engine (Section 9) and Endpoint Intelligence (Section 20).

Deliberately simple, transparent, keyword/heuristic scoring over a
hostname - every point awarded comes with a stated reason, because a
hunter (and Section 27's "Why This Matters" panel) needs to see *why*
something was prioritized, not just a black-box number.

This never claims a vulnerability exists - only that an asset is worth a
human's attention sooner rather than later.

Weights are calibrated so a single strong signal (auth, api, admin,
payment, graphql) alone reaches HIGH, matching the worked example in the
product spec (Section 9): "accounts.example.com" -> Priority: HIGH ->
"Authentication functionality detected" -> "Inspect login, registration,
password-reset and session flows."
"""
from __future__ import annotations

from dataclasses import dataclass, field

HIGH_PRIORITY_THRESHOLD = 40
MEDIUM_PRIORITY_THRESHOLD = 20

_SIGNALS: list[tuple[tuple[str, ...], int, str, str, str]] = [
    (
        ("auth", "login", "sso", "identity", "iam", "account", "accounts"),
        45,
        "auth",
        "Authentication functionality detected.",
        "Inspect login, registration, password-reset and session flows.",
    ),
    (
        ("api", "rest"),
        42,
        "api",
        "This host appears to expose an API. APIs are often useful places to inspect authorization and object-level access controls.",
        "Map the API endpoints.",
    ),
    (
        ("admin", "manage", "internal", "backoffice", "console"),
        40,
        "admin",
        "Administrative-style interface detected.",
        "Verify this interface enforces role/privilege checks before deeper review.",
    ),
    (
        ("graphql",),
        40,
        "graphql",
        "GraphQL endpoint detected.",
        "Enumerate the schema (introspection) and review query authorization.",
    ),
    (
        ("payment", "billing", "checkout", "pay"),
        38,
        "payment",
        "Payment/billing functionality detected.",
        "Review authorization around financial actions and object ownership.",
    ),
    (
        ("portal", "profile", "dashboard"),
        26,
        "account",
        "Account/portal functionality detected.",
        "Check for horizontal access control issues between user accounts.",
    ),
    (
        ("upload", "files", "media", "assets", "cdn"),
        24,
        "upload",
        "Upload/file-handling functionality detected.",
        "Inspect file upload validation, storage, and access controls.",
    ),
    (
        ("ws", "socket", "realtime", "live"),
        22,
        "ws",
        "WebSocket/real-time service indicator.",
        "Inspect connection auth and message-level authorization.",
    ),
    (
        ("dev", "staging", "stage", "test", "uat", "qa", "sandbox", "preprod", "beta"),
        20,
        "dev",
        "Development/staging indicator.",
        "Staging environments sometimes carry weaker controls - confirm program scope before testing.",
    ),
]


@dataclass
class PriorityResult:
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    category: str | None = None
    recommended_action: str | None = None

    @property
    def level(self) -> str:
        if self.score >= HIGH_PRIORITY_THRESHOLD:
            return "HIGH"
        if self.score >= MEDIUM_PRIORITY_THRESHOLD:
            return "MEDIUM"
        return "LOW"


def score_hostname(hostname: str) -> PriorityResult:
    host = hostname.lower()
    label = host.split(".")[0]

    result = PriorityResult()
    best_category: str | None = None
    best_action: str | None = None
    best_points = -1

    for keywords, points, category, reason, action in _SIGNALS:
        if any(kw in label for kw in keywords):
            result.score += points
            result.reasons.append(reason)
            if points > best_points:
                best_points = points
                best_category = category
                best_action = action

    if not result.reasons:
        result.reasons.append("No high-signal keywords in hostname; treat as standard-priority until inspected.")
        result.recommended_action = "Confirm liveness and run technology detection before deeper investigation."
    else:
        result.recommended_action = best_action
        result.category = best_category

    result.score = min(result.score, 100)
    return result
