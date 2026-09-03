"""
Vajra Access Control Workbench (Section 17) - the teaching content.

Section 17 asks Vajra to teach four things while the hunter compares
responses: horizontal access control, vertical access control, object
ownership, and role boundaries. This is the static curriculum for each;
the workbench service pairs it with the project's real captured requests.
Nothing here executes a request - "use controlled accounts and authorized
environments only" (Section 17).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TestType:
    key: str
    name: str
    definition: str
    how_to_set_up: tuple[str, ...]
    signals_worth_a_finding: tuple[str, ...]
    evidence_needed: tuple[str, ...]


TEST_TYPES: tuple[TestType, ...] = (
    TestType(
        key="horizontal",
        name="Horizontal access control",
        definition=(
            "Whether one user can reach another user's data or actions at the same privilege level - "
            "the classic IDOR / BOLA shape."
        ),
        how_to_set_up=(
            "With controlled account A, capture a request for an object A owns (note its identifier).",
            "Re-send the exact same request shape as controlled account B, still pointing at A's object identifier.",
            "Compare: did B receive A's data, or was it denied?",
        ),
        signals_worth_a_finding=(
            "B receives a 2xx with A's object data (same JSON shape, comparable size).",
            "B can modify or delete an object it does not own.",
            "The only thing that changed between allowed and denied was the identifier, not the identity.",
        ),
        evidence_needed=(
            "Both request/response pairs, tokens masked, with the controlled-identity name on each.",
            "Confirmation the returned data actually belongs to the other controlled account.",
        ),
    ),
    TestType(
        key="vertical",
        name="Vertical access control",
        definition=(
            "Whether a lower-privileged user can reach functionality intended for a higher-privileged role "
            "(privilege escalation)."
        ),
        how_to_set_up=(
            "Identify an action that should require elevated privilege (admin panel, user management, config).",
            "Capture it as the privileged controlled account to learn the exact request.",
            "Re-send the same request as a low-privilege controlled account.",
        ),
        signals_worth_a_finding=(
            "The low-privilege account's request succeeds (2xx) and performs the privileged action.",
            "Only a client-side control (hidden menu, disabled button) stood between the roles.",
        ),
        evidence_needed=(
            "The privileged and low-privilege request/response pairs side by side.",
            "Proof the low-privilege session is genuinely low-privilege (e.g. its own role in a /me response).",
        ),
    ),
    TestType(
        key="object_ownership",
        name="Object ownership",
        definition=(
            "Whether the server checks that the caller owns the specific object, or only that the object "
            "exists and the caller is authenticated."
        ),
        how_to_set_up=(
            "Find an endpoint that takes an object identifier and returns or changes that object.",
            "Request an object you own, then an object owned by a second controlled account.",
            "Try both a valid-but-unowned identifier and a non-existent one to see how responses differ.",
        ),
        signals_worth_a_finding=(
            "Owned and unowned identifiers return the same successful response.",
            "Unowned returns 200 while non-existent returns 404 - the server knows the object but not the owner.",
        ),
        evidence_needed=(
            "Responses for owned / unowned / non-existent identifiers from the same identity.",
            "The ownership relationship between each identifier and each controlled account.",
        ),
    ),
    TestType(
        key="role_boundary",
        name="Role boundary",
        definition=(
            "How one endpoint's behavior changes across roles - which fields, records, or actions each role "
            "may see or perform."
        ),
        how_to_set_up=(
            "Pick an endpoint used by more than one role (list views and search endpoints are good candidates).",
            "Capture it once per controlled role.",
            "Compare the response bodies field by field, not just the status code.",
        ),
        signals_worth_a_finding=(
            "A lower role's response includes fields or records that role should not see.",
            "A write/filter parameter accepted from a privileged role is also honoured for a lower role.",
        ),
        evidence_needed=(
            "One captured response per role, with the identity name on each.",
            "A clear statement of which returned field or record crosses the boundary.",
        ),
    ),
)
