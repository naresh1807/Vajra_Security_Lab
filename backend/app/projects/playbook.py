"""
The per-project Hunt Playbook (Section 42: "User creates custom workflows").

A plain ordered checklist of hunt steps, seeded from a default
authorized-bug-bounty methodology and fully editable by the hunter. Not a
gate on anything - it's the hunter's own working notes, tracked so a long
engagement doesn't lose its place.
"""
from __future__ import annotations

import uuid

MAX_STEPS = 60
MAX_STEP_TEXT = 300

DEFAULT_PLAYBOOK_STEPS: tuple[str, ...] = (
    "Confirm the program's scope, rules, and testing restrictions in ScopeGuard.",
    "Run recon; check every discovered host against ScopeGuard before touching it.",
    "Prioritize the attack surface - note auth, API, admin, upload, and payment hosts.",
    "Analyze in-scope JavaScript for routes, config references, and masked secrets.",
    "Map API endpoints and parameters; flag every endpoint that takes an object identifier.",
    "Save at least two controlled test identities in the HTTP Inspector.",
    "Send baseline authenticated requests to the interesting endpoints.",
    "Run the Analyzer on each response; triage the Needs-Review and Potential-Finding results.",
    "Walk the Authentication Flow Analyzer's manual-review checks for each observed stage.",
    "Test access control (horizontal, vertical, object ownership) with the Workbench and Diff.",
    "For each candidate: work the false-positive checklist, attach evidence, write observed vs. potential impact.",
    "Generate the report and verify the evidence bundle's checksums before sharing.",
)


def default_playbook() -> list[dict]:
    return [{"id": uuid.uuid4().hex[:12], "text": text, "done": False} for text in DEFAULT_PLAYBOOK_STEPS]


class PlaybookError(Exception):
    pass


def validate_playbook(raw: object) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise PlaybookError("Playbook must be a list of steps.")
    if len(raw) > MAX_STEPS:
        raise PlaybookError(f"A playbook can have at most {MAX_STEPS} steps.")

    cleaned: list[dict] = []
    seen_ids: set[str] = set()
    for i, step in enumerate(raw):
        if not isinstance(step, dict):
            raise PlaybookError(f"Playbook step #{i + 1} must be an object.")
        text = step.get("text")
        if not isinstance(text, str) or not text.strip():
            raise PlaybookError(f"Playbook step #{i + 1} needs non-empty text.")
        step_id = step.get("id")
        if not isinstance(step_id, str) or not step_id or step_id in seen_ids:
            step_id = uuid.uuid4().hex[:12]
        seen_ids.add(step_id)
        cleaned.append({"id": step_id, "text": text.strip()[:MAX_STEP_TEXT], "done": bool(step.get("done"))})
    return cleaned
