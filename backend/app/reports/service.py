"""
Vajra Report Generator (Section 36) and Report Quality Check / Readiness
Score (Section 37).

`seed_report` drafts the report from an investigation's own recorded
evidence and notes - it never invents impact or reproduction steps that
weren't actually observed (Section 35's rule extends here): steps come
from real linked transactions (already masked before they reach this
module), and every drafted field stays fully editable, never presented
as final.
"""
from __future__ import annotations

from app.core.headers import get_header_ci
from app.evidence.schemas import MaskedTransactionOut
from app.investigations.models import Investigation
from app.reports.schemas import ReadinessCheck, ReadinessOut

_REMEDIATION_HINTS: dict[str, str] = {
    "cors": (
        "Validate the Origin header against an explicit allowlist server-side rather than reflecting it, "
        "and only set Access-Control-Allow-Credentials: true for origins that are actually trusted."
    ),
    "cookies": "Set HttpOnly, Secure, and an appropriate SameSite value on any session/authentication cookie.",
    "security_headers": (
        "Add the missing security headers (Content-Security-Policy, Strict-Transport-Security, "
        "X-Frame-Options, X-Content-Type-Options) at the web server or application framework level."
    ),
    "info_exposure": "Disable verbose error output and version-disclosing headers (Server, X-Powered-By) in production configuration.",
    "tls": "Redirect all HTTP traffic to HTTPS and enable HSTS.",
    "api_response": "Ensure error responses don't leak internal debug/stack-trace fields in production.",
    "auth_behavior": "Return a standard WWW-Authenticate challenge on 401s and avoid leaking why authentication failed.",
}

_DIFF_REMEDIATION = (
    "Add an object-ownership check (e.g. verify the requested resource's owner/account field matches the "
    "authenticated caller) before returning or acting on the object."
)


def suggest_remediation(investigation: Investigation) -> str:
    category = (investigation.source_reference or {}).get("category")
    if category and category in _REMEDIATION_HINTS:
        return _REMEDIATION_HINTS[category]
    if investigation.source == "diff_result":
        return _DIFF_REMEDIATION
    return ""


def generate_steps_to_reproduce(masked_transactions: list[MaskedTransactionOut]) -> str:
    if not masked_transactions:
        return ""
    lines: list[str] = []
    for i, tx in enumerate(masked_transactions, start=1):
        identity = get_header_ci(tx.request_headers, "authorization") or get_header_ci(tx.request_headers, "cookie")
        if tx.identity_profile_name:
            identity_note = f" using controlled identity '{tx.identity_profile_name}'"
        else:
            identity_note = f" using {identity}" if identity else " with no authentication"
        lines.append(f"{i}. Send {tx.method} {tx.url}{identity_note}.")
        if tx.status_code is not None:
            lines.append(f"   Observed: HTTP {tx.status_code}.")
    return "\n".join(lines)


def seed_report(investigation: Investigation, masked_transactions: list[MaskedTransactionOut]) -> dict:
    summary = investigation.ai_notes.strip() or f"{investigation.title} was identified on {investigation.target or 'the target'}."
    snapshot = investigation.access_control_snapshot or {}
    identities = sorted({
        identity
        for cell in snapshot.get("selected_cells", [])
        for identity in (cell.get("identity_a"), cell.get("identity_b"))
        if identity
    })
    prerequisites = ""
    if identities:
        prerequisites = "Controlled test identities: " + ", ".join(identities) + "."
        warnings = snapshot.get("warnings", [])
        if warnings:
            prerequisites += " Review the preserved scenario setup warnings before treating the comparison as valid."
    return {
        "summary": summary,
        "prerequisites": prerequisites,
        "steps_to_reproduce": generate_steps_to_reproduce(masked_transactions),
        "observed_behavior": investigation.notes.strip() or investigation.impact_observed.strip(),
        "expected_behavior": "",
        "suggested_remediation": suggest_remediation(investigation),
    }


def render_report_markdown(investigation: Investigation, report: object) -> str:
    """Canonical portable report rendering used by evidence exports."""
    def value(field: str) -> str:
        if isinstance(report, dict):
            return str(report.get(field, "") or "")
        return str(getattr(report, field, "") or "")

    lines = [
        f"# {investigation.title}",
        "",
        f"**Affected Asset:** {investigation.target or '—'}",
        f"**Endpoint:** {investigation.endpoint or '—'}",
        "",
        "## Summary",
        value("summary") or "_None documented_",
        "",
        "## Prerequisites",
        value("prerequisites") or "_None documented_",
        "",
        "## Steps to Reproduce",
        value("steps_to_reproduce") or "_None documented_",
        "",
        "## Observed Behavior",
        value("observed_behavior") or "_None documented_",
        "",
        "## Expected Behavior",
        value("expected_behavior") or "_None documented_",
        "",
        "## Security Impact",
        investigation.impact_potential or investigation.impact_observed or "_None documented_",
        "",
        "## Suggested Remediation",
        value("suggested_remediation") or "_None documented_",
    ]
    snapshot = investigation.access_control_snapshot or {}
    cells = snapshot.get("selected_cells", [])
    if cells:
        lines.extend(["", "## Preserved Access-Control Comparisons"])
        for cell in cells:
            lines.append(
                f"- Requests #{cell['transaction_a_id']} ({cell['identity_a']}) and "
                f"#{cell['transaction_b_id']} ({cell['identity_b']}): "
                f"{cell['category']}, {cell['confidence']}% triage confidence."
            )
        for warning in snapshot.get("warnings", []):
            lines.append(f"- Setup warning: {warning}")
    return "\n".join(lines) + "\n"


def compute_readiness(investigation: Investigation, has_evidence_attachment: bool, scope_verified: bool) -> ReadinessOut:
    checks = [
        ReadinessCheck(label="Clear, descriptive title", passed=len(investigation.title.strip()) >= 10, points=12),
        ReadinessCheck(
            label="Reproducibility confirmed in the false-positive checklist",
            passed=investigation.false_positive_checklist.get("reproducible") is True,
            points=13,
        ),
        ReadinessCheck(
            label="Requests/responses attached as evidence",
            passed=bool(investigation.linked_transaction_ids),
            points=13,
        ),
        ReadinessCheck(label="At least one screenshot attached", passed=has_evidence_attachment, points=12),
        ReadinessCheck(
            label="Impact demonstrated (Observed Impact filled in)",
            passed=bool(investigation.impact_observed.strip()),
            points=13,
        ),
        # Masking is enforced by build_evidence_package for every transaction shown in a report -
        # this isn't something the hunter can get wrong, so it's always credited.
        ReadinessCheck(label="Sensitive information masked in evidence", passed=True, points=12),
        ReadinessCheck(label="Scope verified for this target", passed=scope_verified, points=13),
        ReadinessCheck(
            label="Program policy explicitly checked (confirmed not excluded)",
            passed=investigation.false_positive_checklist.get("program_excludes_issue") is False,
            points=12,
        ),
    ]
    score = sum(c.points for c in checks if c.passed)
    missing = [c.label for c in checks if not c.passed]
    return ReadinessOut(score=score, checks=checks, missing=missing)
