"""
Vajra Investigation Workspace (Section 24), False Positive Engine
(Section 34), and Finding Confidence (Section 33).

Deliberately does NOT try to auto-decide whether something is a false
positive from the checklist answers - Section 34 frames these six
questions as prompts for the human, not inputs to an algorithm. The one
thing this module will do is point out when an answer is *logically in
tension* with the investigation still being open (e.g. "the program
excludes this issue" but status is still OPEN) - a nudge, never an
auto-close.
"""
from __future__ import annotations

from app.investigations.models import FALSE_POSITIVE_QUESTIONS, Investigation
from app.investigations.schemas import InvestigationOut


PRACTICE_SIGNALS: dict[str, tuple[str, ...]] = {
    "idor": ("idor", "bola", "object", "authorization", "access control", "ownership"),
    "cors": ("cors", "origin", "cross-origin"),
    "cookies": ("cookie", "session", "httponly", "samesite", "secure flag"),
    "headers": ("header", "csp", "hsts", "x-frame", "content-security-policy"),
    "info-exposure": ("exposure", "stack trace", "verbose", "debug", "error", "sensitive"),
}


def recommended_practice_labs(inv: Investigation) -> list[str]:
    context = " ".join(
        [inv.title, inv.target, inv.endpoint, inv.ai_notes, inv.notes, str(inv.source_reference)]
    ).lower()
    matches = [lab_id for lab_id, terms in PRACTICE_SIGNALS.items() if any(term in context for term in terms)]
    # A useful contextual default for investigations whose title is still
    # generic; never overwhelm the workspace with the whole catalog.
    return matches[:3] or ["idor"]


def compute_missing_evidence(inv: Investigation) -> list[str]:
    missing: list[str] = []

    if not inv.linked_transaction_ids:
        missing.append("No evidence (requests/responses) attached yet.")

    answered = sum(1 for v in inv.false_positive_checklist.values() if v is not None)
    total = len(FALSE_POSITIVE_QUESTIONS)
    if answered < total:
        missing.append(f"{total - answered} of {total} false-positive checks not yet answered.")

    if not inv.impact_observed.strip():
        missing.append("Observed impact not documented yet.")

    if inv.status == "open" and not inv.notes.strip():
        missing.append("No investigation notes recorded yet - what did you actually check?")

    return missing


def compute_false_positive_hint(checklist: dict[str, bool | None]) -> str | None:
    if checklist.get("program_excludes_issue") is True:
        return "You indicated the program explicitly excludes this issue - this is likely out of scope regardless of technical validity."
    if checklist.get("behavior_intended") is True:
        return "You indicated this behavior is intended - this may be a false positive rather than a bug."
    if checklist.get("object_belongs_to_other_account") is False:
        return "You indicated the object does NOT belong to a different controlled account - this may mean access control isn't actually being bypassed here."
    if checklist.get("reproducible") is False:
        return "You indicated this isn't reliably reproducible - most programs won't accept a report you can't reproduce."
    return None


def to_out(inv: Investigation) -> InvestigationOut:
    values = {
        field: getattr(inv, field)
        for field in InvestigationOut.model_fields
        if field not in {"missing_evidence", "false_positive_hint", "false_positive_questions", "recommended_practice_labs"}
    }
    values["access_control_snapshot"] = values.get("access_control_snapshot") or {}
    values["practice_progress"] = values.get("practice_progress") or {}
    base = InvestigationOut.model_validate(values)
    base.missing_evidence = compute_missing_evidence(inv)
    base.false_positive_hint = compute_false_positive_hint(inv.false_positive_checklist)
    base.false_positive_questions = FALSE_POSITIVE_QUESTIONS
    base.recommended_practice_labs = recommended_practice_labs(inv)
    return base
