"""
Vajra Hunt Copilot (Section 25) - rule-based knowledge engine, plus the
seam where a real LLM plugs in (Section 46's "provider-independent AI
abstraction", Phase 11).

Structured explanations (explain_asset/explain_header) stay rule-based
*always*, on purpose - they're deterministic and auditable, and a live
model wouldn't improve a lookup this small. The `AIProvider` seam below
is specifically for open-ended Hunt Copilot questions (Section 25:
"What should I inspect next?", "Explain this in Telugu.", "How should I
document this finding?") where a live model earns its keep over a fixed
knowledge base. See `ask_hunt_copilot()` at the bottom for how the two
halves compose: free-form questions try a real provider first and fall
back to a plain, honest message - never a fabricated answer - when none
is configured or reachable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
import os

from app.core.config import settings


@dataclass
class Explanation:
    what_found: str
    why_it_matters: str
    what_to_check: list[str]
    false_positive_notes: list[str]
    evidence_needed: list[str]
    mini_lesson_title: str | None = None
    mini_lesson: str | None = None


_ASSET_KNOWLEDGE: dict[str, Explanation] = {
    "api": Explanation(
        what_found="An API host or endpoint.",
        why_it_matters=(
            "APIs are often where authorization and object-level access controls live. Many real-world bugs "
            "(especially broken object-level authorization) surface first in API responses rather than in the UI."
        ),
        what_to_check=[
            "Map the API's endpoints and group them by resource (users, orders, files, ...).",
            "Identify endpoints that take an object identifier (e.g. /api/orders/{id}).",
            "Compare responses for objects you own vs. objects owned by a second controlled test account.",
        ],
        false_positive_notes=[
            "The endpoint may be intentionally public (e.g. a public catalog).",
            "The object identifier may not map to sensitive or user-specific data.",
        ],
        evidence_needed=[
            "Two authenticated requests (different accounts) against the same endpoint/object.",
            "The raw request/response pairs, with tokens masked before saving.",
        ],
        mini_lesson_title="60-second concept: BOLA / IDOR",
        mini_lesson=(
            "A Broken Object Level Authorization (IDOR is the classic case) occurs when an API exposes an object "
            "identifier and fails to verify the current caller is actually authorized to access that specific object."
        ),
    ),
    "auth": Explanation(
        what_found="An authentication-related host or flow (login, SSO, identity).",
        why_it_matters=(
            "Authentication surfaces control who gets in and as whom. Weaknesses here (session fixation, "
            "predictable reset tokens, missing rate limiting) tend to have outsized impact."
        ),
        what_to_check=[
            "Map the full flow: registration -> verification -> login -> session creation -> password reset -> logout.",
            "Check what happens to old sessions after a password change or logout.",
            "Look at how a password-reset token is generated, delivered, and invalidated.",
        ],
        false_positive_notes=[
            "Rate limiting or lockouts may exist server-side but not be visible in a single request.",
            "Behavior may be an intentional design choice documented by the program.",
        ],
        evidence_needed=[
            "A reproducible step-by-step flow using your own controlled test account.",
            "Timestamps showing session validity before/after the relevant action.",
        ],
        mini_lesson_title="60-second concept: Session Invalidation",
        mini_lesson=(
            "A secure app invalidates old sessions/tokens after sensitive account events (password change, logout, "
            "email change). If an old session keeps working afterward, that is worth documenting."
        ),
    ),
    "account": Explanation(
        what_found="An account or user-portal surface.",
        why_it_matters="Account/portal pages frequently expose per-user data and actions - prime territory for horizontal access-control checks.",
        what_to_check=[
            "Identify every action that references 'your' data implicitly (an ID in a URL, a hidden form field, a cookie).",
            "With two controlled test accounts, try accessing account A's resources while authenticated as account B.",
        ],
        false_positive_notes=["The data returned may be intentionally shared/public between users."],
        evidence_needed=["Side-by-side request/response evidence from two controlled accounts."],
        mini_lesson_title="60-second concept: Horizontal vs. Vertical Access Control",
        mini_lesson=(
            "Horizontal access control keeps User A out of User B's data at the same privilege level. Vertical "
            "access control keeps a normal user out of admin-only actions. Both are commonly broken independently."
        ),
    ),
    "admin": Explanation(
        what_found="An administrative-style interface.",
        why_it_matters="Admin panels concentrate privileged functionality; a role-check gap here has outsized impact.",
        what_to_check=[
            "Confirm whether the panel is reachable without an authenticated privileged session.",
            "If reachable while authenticated as a low-privilege user, note exactly which actions succeed.",
        ],
        false_positive_notes=["The panel may already be correctly gated and simply resolve on this hostname."],
        evidence_needed=["Screenshot/response showing the privilege level of the session used."],
        mini_lesson_title="60-second concept: Vertical Privilege Escalation",
        mini_lesson="Vertical privilege escalation is when a lower-privileged user reaches functionality meant for a higher-privileged role.",
    ),
    "upload": Explanation(
        what_found="File-upload or media-handling functionality.",
        why_it_matters="Upload handling touches storage, content-type trust, and sometimes execution paths.",
        what_to_check=[
            "Check what file types/extensions are accepted and how they're validated.",
            "Check where uploaded files are stored and whether access to them is authorization-checked.",
        ],
        false_positive_notes=["Restrictive server-side validation may already exist even if the client-side check is weak."],
        evidence_needed=["The upload request, the resulting storage URL, and any access-control test around it."],
        mini_lesson_title="60-second concept: Unrestricted File Upload",
        mini_lesson="An unrestricted upload occurs when an app fails to validate file type/content, potentially allowing stored malicious content or path traversal.",
    ),
    "graphql": Explanation(
        what_found="A GraphQL endpoint.",
        why_it_matters="GraphQL concentrates many operations behind one endpoint - authorization must be enforced per-field/resolver, which is easy to miss.",
        what_to_check=[
            "Check whether introspection is enabled.",
            "Enumerate queries/mutations and test object-level authorization on each that takes an ID.",
        ],
        false_positive_notes=["Introspection being enabled is informational, not itself a vulnerability."],
        evidence_needed=["The schema (if introspectable) and per-operation authorization test results."],
        mini_lesson_title="60-second concept: GraphQL Authorization",
        mini_lesson="Unlike REST, a single GraphQL endpoint can expose many operations - each resolver needs its own authorization check, and it's common for one to be missed.",
    ),
    "ws": Explanation(
        what_found="A WebSocket or real-time service indicator.",
        why_it_matters="Real-time channels sometimes skip the authorization checks applied to normal HTTP routes.",
        what_to_check=["Check how the connection authenticates.", "Check whether message-level actions re-verify authorization."],
        false_positive_notes=["The channel may only carry non-sensitive, already-public data."],
        evidence_needed=["Captured connection handshake and a sample of authorized vs. unauthorized message attempts."],
        mini_lesson_title="60-second concept: WebSocket Authorization",
        mini_lesson="A WebSocket connection is often authenticated once at handshake - but every message/action sent afterward still needs its own authorization check.",
    ),
    "dev": Explanation(
        what_found="A development/staging/QA indicator.",
        why_it_matters="Non-production environments sometimes ship with weaker auth, debug endpoints, or verbose errors.",
        what_to_check=["Confirm this host is in program scope before testing further.", "Look for debug endpoints, verbose stack traces, or default credentials."],
        false_positive_notes=["Some programs explicitly exclude staging/dev environments - check program rules."],
        evidence_needed=["Confirmation the host is in-scope, plus any behavior differing from production."],
        mini_lesson_title="60-second concept: Environment Parity Risk",
        mini_lesson="Staging/dev environments frequently drift from production hardening (debug mode, relaxed auth), even though they run the same codebase.",
    ),
    "payment": Explanation(
        what_found="Payment or billing functionality.",
        why_it_matters="Financial actions carry direct business impact - authorization and amount/ownership validation matter most here.",
        what_to_check=["Check whether amounts, currency, or discounts can be manipulated client-side.", "Check ownership validation on billing objects (invoices, payment methods)."],
        false_positive_notes=["Server-side re-validation may already occur even if the client sends manipulable values."],
        evidence_needed=["Before/after request-response pairs showing the manipulated vs. accepted value."],
        mini_lesson_title="60-second concept: Business Logic Abuse",
        mini_lesson="Business logic flaws occur when an app trusts client-supplied values (price, quantity, state) that should be re-validated server-side.",
    ),
}

_GENERIC_ASSET = Explanation(
    what_found="A newly discovered host.",
    why_it_matters=(
        "Different subdomains can host separate applications, APIs, authentication systems, staging environments, "
        "or administrative interfaces - each with its own attack surface."
    ),
    what_to_check=["Confirm whether the host is alive.", "Identify its technology stack.", "Look for login forms, APIs, or file upload functionality."],
    false_positive_notes=["The host may simply be a redirect or a parked/unused DNS record."],
    evidence_needed=["Liveness check result and a technology fingerprint."],
)

_HEADER_KNOWLEDGE: dict[str, Explanation] = {
    "authorization": Explanation(
        what_found="An Authorization header.",
        why_it_matters=(
            "This header commonly carries an access token (Bearer/JWT/Basic) used to identify the caller to an "
            "API. Authorization flaws can occur when a server trusts the identifier inside the token but fails "
            "to verify the caller actually owns the resource being requested."
        ),
        what_to_check=[
            "Identify the token type (Bearer/JWT/Basic).",
            "If a JWT, inspect (don't forge) its claims for role/user-id fields.",
            "Test whether swapping the token between two controlled accounts changes which data is returned.",
        ],
        false_positive_notes=["A shared/service token intentionally has broad access."],
        evidence_needed=["The two compared requests/responses, with the token value masked."],
    ),
    "set-cookie": Explanation(
        what_found="A Set-Cookie response header.",
        why_it_matters="Cookie attributes (HttpOnly, Secure, SameSite) determine exposure to XSS/CSRF-style abuse of the session.",
        what_to_check=["Check for HttpOnly (blocks JS access), Secure (HTTPS-only), and SameSite (CSRF exposure).", "Check the cookie's expiry/session lifetime."],
        false_positive_notes=["A non-sensitive, purely functional cookie (e.g. UI theme) doesn't need the same scrutiny as a session cookie."],
        evidence_needed=["The full Set-Cookie header value, with the cookie's actual value masked."],
    ),
    "access-control-allow-origin": Explanation(
        what_found="A CORS header (Access-Control-Allow-Origin).",
        why_it_matters="An overly permissive CORS policy (wildcard or reflected origin) combined with credentialed requests can let a malicious site read authenticated responses on a victim's behalf.",
        what_to_check=["Check whether the origin is reflected/wildcarded.", "Check whether Access-Control-Allow-Credentials is also true."],
        false_positive_notes=["A wildcard origin on a fully public, unauthenticated API is not a control issue by itself."],
        evidence_needed=["The response headers for a request sent with an arbitrary Origin."],
    ),
}


def explain_asset(hostname: str, priority_category: str | None) -> Explanation:
    if priority_category and priority_category in _ASSET_KNOWLEDGE:
        return _ASSET_KNOWLEDGE[priority_category]
    return _GENERIC_ASSET


def explain_header(header_name: str) -> Explanation | None:
    return _HEADER_KNOWLEDGE.get(header_name.strip().lower())


class AIProvider(Protocol):
    """Extension seam for a real, provider-independent AI backend (Section 46).

    Any provider (Anthropic, or another vendor entirely) implements just
    this one async method; `ask_hunt_copilot()` below is the only caller,
    so swapping or adding a provider never touches the router or frontend.
    """

    name: str

    async def ask(self, question: str, context: dict) -> str: ...


class RuleBasedProvider:
    """Default Hunt Copilot provider - deterministic, auditable, offline."""

    name = "rule_based"

    def explain_asset(self, hostname: str, priority_category: str | None) -> Explanation:
        return explain_asset(hostname, priority_category)

    def explain_header(self, header_name: str) -> Explanation | None:
        return explain_header(header_name)

    async def ask(self, question: str, context: dict) -> str:
        return (
            "Free-form Hunt Copilot chat needs a configured AI provider - set GEMINI_API_KEY or "
            "ANTHROPIC_API_KEY and restart the backend to enable it. Meanwhile, click "
            "Explain on an asset or a response header for a rule-based answer, or check the "
            "Recommended Next Action panel above."
        )


default_provider = RuleBasedProvider()


async def ask_hunt_copilot(question: str, context: dict) -> tuple[str, str]:
    """Try a live provider first; fall back to a plain, honest explanation
    of *why* - never a fabricated answer - if none is configured or reachable.

    Returns (answer, provider_name) so callers can be transparent about
    which one actually answered.
    """
    preferred = settings.ai_provider.lower()
    providers: list[AIProvider] = []
    last_error: Exception | None = None
    if preferred not in {"auto", "gemini", "anthropic"}:
        return "Invalid VAJRA_AI_PROVIDER setting; use auto, gemini, or anthropic.", default_provider.name
    if preferred in {"auto", "gemini"} and (preferred == "gemini" or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        try:
            from app.copilot.gemini_provider import GeminiProvider
            providers.append(GeminiProvider())
        except Exception as exc:  # key/configuration problem
            last_error = exc
    if preferred in {"auto", "anthropic"}:
        try:
            from app.copilot.anthropic_provider import AnthropicProvider
            providers.append(AnthropicProvider())
        except Exception as exc:
            last_error = exc
    for provider in providers:
        try:
            return await provider.ask(question, context), provider.name
        except Exception as exc:  # noqa: BLE001 - fail over without fabricating
            last_error = exc
    return await _fallback_message(last_error or RuntimeError("No AI provider configured")), default_provider.name


_NO_CREDENTIALS_MESSAGE = (
    "Free-form Hunt Copilot chat needs API credentials - set GEMINI_API_KEY or ANTHROPIC_API_KEY "
    "and restart the backend. Meanwhile, click Explain on an "
    "asset or header for a rule-based answer."
)


async def _fallback_message(exc: Exception) -> str:
    import anthropic

    # No credentials found at all (no env var, no `ant auth login` profile) is a client-side
    # pre-flight check the SDK raises as a plain TypeError *before* any network call - it never
    # reaches the server, so it is NOT an anthropic.AuthenticationError (that's reserved for a
    # real 401 response, i.e. a *bad* key rather than a *missing* one). Confirmed by testing
    # against this exact SDK version with zero credentials configured.
    if isinstance(exc, TypeError) and "Could not resolve authentication method" in str(exc):
        return _NO_CREDENTIALS_MESSAGE
    if isinstance(exc, anthropic.AuthenticationError):
        return _NO_CREDENTIALS_MESSAGE
    if isinstance(exc, anthropic.RateLimitError):
        return "The AI provider is rate-limited right now - try again in a moment."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Couldn't reach the AI provider (network error) - try again in a moment."
    if isinstance(exc, anthropic.APIStatusError):
        return f"The AI provider returned an error ({exc.status_code}) - try again, or use the rule-based Explain buttons meanwhile."
    return "The AI provider returned an unexpected error - try again, or use the rule-based Explain buttons meanwhile."
