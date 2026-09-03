"""
Vajra Analyzer (Section 22).

Every check here is a pure function over already-fetched HTTP data - no
network calls of its own, easy to unit test. Findings are classified using
exactly the levels the spec calls for: INFORMATIONAL, INTERESTING,
NEEDS_REVIEW, POTENTIAL_FINDING - never "confirmed vulnerability" (Section
34/35: a scanner result is a signal, not a finding, until a human
validates it).

Implemented with real, distinct logic:
    Security Header Analyzer, Cookie Analyzer, CORS Analyzer,
    TLS Analyzer (scheme-level only - see its docstring), Information
    Exposure Analyzer, API Response Analyzer, Authentication Behavior
    Analyzer. Public metadata analysis is implemented separately over persisted
    robots.txt and sitemap evidence in analyzer/metadata.py.

A distinct Configuration Analyzer is not implemented because its signals would
duplicate Information Exposure at the scope of a single HTTP transaction.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.core.headers import get_header_ci as _ci_get


class Classification:
    INFORMATIONAL = "informational"
    INTERESTING = "interesting"
    NEEDS_REVIEW = "needs_review"
    POTENTIAL_FINDING = "potential_finding"


@dataclass
class AnalyzerFinding:
    category: str
    classification: str
    title: str
    description: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class AnalyzerInput:
    url: str
    status_code: int | None
    request_headers: dict[str, str]
    response_headers: dict[str, str]
    response_cookies: list[str]
    body: str


_SECURITY_HEADER_SPECS: list[tuple[str, str, str, str]] = [
    (
        "content-security-policy",
        Classification.NEEDS_REVIEW,
        "Missing Content-Security-Policy",
        "CSP restricts which sources scripts/styles/frames may load from - one of the strongest available "
        "mitigations for the impact of an XSS finding.",
    ),
    (
        "strict-transport-security",
        Classification.NEEDS_REVIEW,
        "Missing Strict-Transport-Security",
        "Without HSTS, a network attacker could potentially downgrade a user from HTTPS to HTTP on this host.",
    ),
    (
        "x-frame-options",
        Classification.INTERESTING,
        "Missing X-Frame-Options",
        "Without this (or a CSP frame-ancestors directive), the page may be embeddable in another site's frame "
        "(clickjacking exposure).",
    ),
    (
        "x-content-type-options",
        Classification.INTERESTING,
        "Missing X-Content-Type-Options",
        "Without 'nosniff', some browsers may MIME-sniff the response body, which has historically enabled "
        "content-type confusion issues.",
    ),
    (
        "referrer-policy",
        Classification.INFORMATIONAL,
        "Missing Referrer-Policy",
        "Without an explicit policy, the browser's default referrer behavior applies, which can leak the full "
        "URL to third-party destinations.",
    ),
]


def analyze_security_headers(data: AnalyzerInput) -> list[AnalyzerFinding]:
    findings = [
        AnalyzerFinding("security_headers", classification, title, desc, [f"No '{header}' header in the response."])
        for header, classification, title, desc in _SECURITY_HEADER_SPECS
        if _ci_get(data.response_headers, header) is None
    ]
    if not findings:
        findings.append(
            AnalyzerFinding(
                "security_headers",
                Classification.INFORMATIONAL,
                "All checked security headers are present",
                "Content-Security-Policy, Strict-Transport-Security, X-Frame-Options, X-Content-Type-Options, "
                "and Referrer-Policy were all found.",
            )
        )
    return findings


def analyze_cookies(data: AnalyzerInput) -> list[AnalyzerFinding]:
    if not data.response_cookies:
        return [AnalyzerFinding("cookies", Classification.INFORMATIONAL, "No cookies set on this response", "")]

    findings = []
    for raw in data.response_cookies:
        name = raw.split("=", 1)[0].strip()
        lower = raw.lower()
        missing = [
            flag
            for flag, needle in (("HttpOnly", "httponly"), ("Secure", "secure"), ("SameSite", "samesite"))
            if needle not in lower
        ]
        if not missing:
            continue
        looks_sensitive = any(k in name.lower() for k in ("sess", "token", "auth", "jwt", "sid", "login"))
        classification = Classification.NEEDS_REVIEW if looks_sensitive else Classification.INTERESTING
        findings.append(
            AnalyzerFinding(
                "cookies",
                classification,
                f"Cookie '{name}' is missing {', '.join(missing)}",
                "HttpOnly blocks JS access to the cookie value, Secure requires HTTPS, and SameSite limits "
                "cross-site sending - missing flags widen the cookie's exposure to XSS/CSRF-style abuse."
                + (" This looks like a session/auth cookie, which raises the stakes." if looks_sensitive else ""),
                [raw],
            )
        )
    if not findings:
        findings.append(
            AnalyzerFinding(
                "cookies", Classification.INFORMATIONAL, "All cookies set with HttpOnly, Secure, and SameSite", ""
            )
        )
    return findings


def analyze_cors(data: AnalyzerInput) -> list[AnalyzerFinding]:
    acao = _ci_get(data.response_headers, "access-control-allow-origin")
    if acao is None:
        return [AnalyzerFinding("cors", Classification.INFORMATIONAL, "No CORS headers on this response", "")]

    acac = (_ci_get(data.response_headers, "access-control-allow-credentials") or "").lower() == "true"
    req_origin = _ci_get(data.request_headers, "origin")

    if req_origin and acao == req_origin:
        classification = Classification.POTENTIAL_FINDING if acac else Classification.NEEDS_REVIEW
        evidence = [f"Request Origin: {req_origin}", f"Access-Control-Allow-Origin: {acao}"]
        if acac:
            evidence.append("Access-Control-Allow-Credentials: true")
        return [
            AnalyzerFinding(
                "cors",
                classification,
                "CORS reflects the request's Origin header" + (" with credentials allowed" if acac else ""),
                "The server echoed back whatever Origin was sent rather than checking it against an allowlist"
                + (
                    ". Combined with Allow-Credentials, a malicious site could potentially read this API's "
                    "authenticated responses on a victim's behalf."
                    if acac
                    else " - worth confirming this isn't intended to be a public, unauthenticated endpoint."
                ),
                evidence,
            )
        ]
    if acao == "*":
        classification = Classification.NEEDS_REVIEW if acac else Classification.INFORMATIONAL
        evidence = ["Access-Control-Allow-Origin: *"] + (["Access-Control-Allow-Credentials: true"] if acac else [])
        return [
            AnalyzerFinding(
                "cors",
                classification,
                "Access-Control-Allow-Origin is wildcarded"
                + (" alongside Allow-Credentials=true (most browsers reject this exact combination, but it still signals sloppy config)" if acac else ""),
                "A wildcard origin is expected and fine for a fully public, unauthenticated API - worth "
                "confirming that's the intent here.",
                evidence,
            )
        ]
    return [
        AnalyzerFinding(
            "cors",
            Classification.INFORMATIONAL,
            "Access-Control-Allow-Origin set to a fixed value",
            f"Access-Control-Allow-Origin: {acao}",
            [f"Access-Control-Allow-Origin: {acao}"],
        )
    ]


def analyze_transport_security(data: AnalyzerInput) -> list[AnalyzerFinding]:
    """Scheme-level only. Vajra doesn't independently renegotiate the TLS
    handshake to inspect cipher suite/protocol version/cert chain - httpx
    already enforces standard certificate verification, so a completed
    HTTPS response here means verification already succeeded."""
    scheme = urlsplit(data.url).scheme.lower()
    if scheme == "http":
        return [
            AnalyzerFinding(
                "tls",
                Classification.POTENTIAL_FINDING,
                "Request was sent over plain HTTP",
                "Traffic - including any credentials, cookies, or tokens - travels unencrypted and can be "
                "intercepted or modified in transit.",
                [f"URL: {data.url}"],
            )
        ]
    if scheme == "https":
        return [
            AnalyzerFinding(
                "tls",
                Classification.INFORMATIONAL,
                "HTTPS with a certificate that validated successfully",
                "Vajra doesn't independently inspect the TLS handshake (cipher suite, protocol version, "
                "certificate chain) - only that the connection succeeded under standard certificate verification.",
            )
        ]
    return []


_ERROR_BODY_MARKERS = (
    "traceback (most recent call last)",
    "stack trace",
    "exception in thread",
    "fatal error:",
    " at line ",
    "django.db.utils",
    "org.springframework",
    "system.exception",
    "unhandled exception",
)
_SENSITIVE_PATH_MARKERS = (".git/", ".env", "wp-config.php", "id_rsa", "web.config", ".ds_store")


def analyze_information_exposure(data: AnalyzerInput) -> list[AnalyzerFinding]:
    findings = []
    body_lower = data.body.lower()

    server = _ci_get(data.response_headers, "server")
    if server and any(ch.isdigit() for ch in server):
        findings.append(
            AnalyzerFinding(
                "info_exposure",
                Classification.INTERESTING,
                "Server header discloses a version number",
                f"Server: {server}",
                [f"Server: {server}"],
            )
        )

    powered_by = _ci_get(data.response_headers, "x-powered-by")
    if powered_by:
        findings.append(
            AnalyzerFinding(
                "info_exposure",
                Classification.INTERESTING,
                "X-Powered-By discloses backend technology",
                f"X-Powered-By: {powered_by}",
                [f"X-Powered-By: {powered_by}"],
            )
        )

    if data.status_code and data.status_code >= 500 and any(m in body_lower for m in _ERROR_BODY_MARKERS):
        findings.append(
            AnalyzerFinding(
                "info_exposure",
                Classification.NEEDS_REVIEW,
                "Response body looks like a verbose error or stack trace",
                "A 5xx response with what looks like framework/language error detail can expose internal "
                "paths, library versions, or application logic.",
            )
        )

    path = urlsplit(data.url).path.lower()
    if data.status_code == 200 and any(m in path for m in _SENSITIVE_PATH_MARKERS):
        findings.append(
            AnalyzerFinding(
                "info_exposure",
                Classification.POTENTIAL_FINDING,
                "A sensitive-file-shaped path returned 200",
                "The requested path matches a pattern commonly associated with sensitive files, and the "
                "server returned 200 OK.",
                [data.url],
            )
        )

    if not findings:
        findings.append(
            AnalyzerFinding("info_exposure", Classification.INFORMATIONAL, "No obvious information-exposure signals", "")
        )
    return findings


def analyze_api_response(data: AnalyzerInput) -> list[AnalyzerFinding]:
    findings = []
    content_type = (_ci_get(data.response_headers, "content-type") or "").lower()
    accept = (_ci_get(data.request_headers, "accept") or "").lower()

    if data.status_code and data.status_code < 400 and "json" in accept and content_type and "json" not in content_type:
        findings.append(
            AnalyzerFinding(
                "api_response",
                Classification.INTERESTING,
                "Client requested JSON but got a different content type",
                f"Accept: {accept} vs. actual Content-Type: {content_type}",
            )
        )

    if data.status_code and 200 <= data.status_code < 300 and not data.body:
        findings.append(
            AnalyzerFinding("api_response", Classification.INFORMATIONAL, "Successful response with an empty body", "")
        )

    if "json" in content_type and data.body:
        try:
            parsed = json.loads(data.body)
            if isinstance(parsed, dict):
                debug_keys = [k for k in parsed if k.lower() in ("stacktrace", "stack_trace", "trace", "debug", "exception")]
                if debug_keys:
                    findings.append(
                        AnalyzerFinding(
                            "api_response",
                            Classification.NEEDS_REVIEW,
                            "JSON response includes a debug/stack-trace-shaped field",
                            f"Field name(s): {', '.join(debug_keys)}",
                            debug_keys,
                        )
                    )
        except (ValueError, TypeError):
            findings.append(
                AnalyzerFinding(
                    "api_response", Classification.INTERESTING, "Content-Type says JSON but the body didn't parse as JSON", ""
                )
            )

    if not findings:
        findings.append(AnalyzerFinding("api_response", Classification.INFORMATIONAL, "No API response anomalies detected", ""))
    return findings


def analyze_auth_behavior(data: AnalyzerInput) -> list[AnalyzerFinding]:
    had_auth_header = _ci_get(data.request_headers, "authorization") is not None
    www_auth = _ci_get(data.response_headers, "www-authenticate")

    if data.status_code == 401:
        if www_auth:
            return [
                AnalyzerFinding(
                    "auth_behavior",
                    Classification.INFORMATIONAL,
                    "401 response includes a WWW-Authenticate challenge",
                    f"WWW-Authenticate: {www_auth}",
                )
            ]
        return [
            AnalyzerFinding(
                "auth_behavior",
                Classification.INTERESTING,
                "401 response without a WWW-Authenticate header",
                "Non-standard, but not unusual for token-based APIs that don't use the WWW-Authenticate "
                "challenge flow.",
            )
        ]
    if data.status_code == 403 and not had_auth_header:
        return [
            AnalyzerFinding(
                "auth_behavior", Classification.INFORMATIONAL, "403 returned without any Authorization header sent", ""
            )
        ]
    return [
        AnalyzerFinding(
            "auth_behavior",
            Classification.INFORMATIONAL,
            "No specific authentication-flow signal from this single response",
            "Compare authenticated vs. unauthenticated requests (Vajra Diff, Phase 7) to learn more.",
        )
    ]


_ALL_ANALYZERS = [
    analyze_security_headers,
    analyze_cookies,
    analyze_cors,
    analyze_transport_security,
    analyze_information_exposure,
    analyze_api_response,
    analyze_auth_behavior,
]


def run_all_analyzers(data: AnalyzerInput) -> list[AnalyzerFinding]:
    findings: list[AnalyzerFinding] = []
    for analyzer in _ALL_ANALYZERS:
        findings.extend(analyzer(data))
    return findings


def count_by_classification(findings: list[AnalyzerFinding]) -> dict[str, int]:
    counts = {
        Classification.INFORMATIONAL: 0,
        Classification.INTERESTING: 0,
        Classification.NEEDS_REVIEW: 0,
        Classification.POTENTIAL_FINDING: 0,
    }
    for f in findings:
        counts[f.classification] = counts.get(f.classification, 0) + 1
    return counts
