"""
Vajra Personal Bug Bounty Skill Map (Sections 39, 40) - pure scoring.

Section 39: "Learning analytics should be derived automatically from
actual hunting" and "No separate course completion is required."
Section 40 names six skills. Every point below traces to a real,
countable action in the database - no quizzes, no self-assessment, and
(like the rest of Vajra) no black-box number: each skill returns the
signal breakdown that produced its score.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalSpec:
    key: str
    label: str
    points_each: int
    cap: int


@dataclass(frozen=True)
class SkillSpec:
    key: str
    label: str
    blurb: str
    next_step: str
    signals: tuple[SignalSpec, ...]


# Section 40's six skills, in its order. Signal caps are tuned so a skill
# reaches "proficient" (50) through a mix of activity, not by repeating one
# action, and "strong" (75+) needs sustained work across several signals.
SKILLS: tuple[SkillSpec, ...] = (
    SkillSpec(
        key="recon",
        label="Recon",
        blurb="Finding and mapping a target's attack surface.",
        next_step="Run recon on a project, then probe and technology-fingerprint the discovered hosts.",
        signals=(
            SignalSpec("completed_recon_jobs", "Recon jobs completed", 7, 42),
            SignalSpec("live_hosts", "Live hosts discovered", 2, 30),
            SignalSpec("projects_with_surface", "Projects with a discovered surface", 9, 28),
        ),
    ),
    SkillSpec(
        key="http",
        label="HTTP",
        blurb="Sending requests and reading what the response tells you.",
        next_step="Send more requests through the HTTP Inspector and run the Analyzer on the responses.",
        signals=(
            SignalSpec("http_requests", "Requests sent", 3, 45),
            SignalSpec("distinct_endpoint_patterns", "Distinct endpoint shapes exercised", 4, 35),
            SignalSpec("requests_with_identity", "Requests sent as a controlled identity", 4, 20),
            SignalSpec("practice", "Contextual HTTP practice", 6, 18),
        ),
    ),
    SkillSpec(
        key="api_analysis",
        label="API Analysis",
        blurb="Understanding an API's endpoints, parameters, and data shapes.",
        next_step="Analyze JS files for routes and open the API Mapper and Parameter Intelligence views.",
        signals=(
            SignalSpec("js_files", "JavaScript files analyzed", 6, 30),
            SignalSpec("discovered_endpoints", "Endpoints inventoried", 1, 35),
            SignalSpec("js_api_routes", "API routes extracted from JS", 2, 30),
            SignalSpec("practice", "Contextual API practice", 6, 18),
        ),
    ),
    SkillSpec(
        key="access_control",
        label="Access Control",
        blurb="Testing whether users can reach data and actions that aren't theirs.",
        next_step="Use the Access Control Workbench: capture a request as two identities and compare in Diff.",
        signals=(
            SignalSpec("scenarios", "Access-control scenarios built", 12, 36),
            SignalSpec("diff_investigations", "Investigations from a Diff / scenario", 10, 30),
            SignalSpec("multi_request_investigations", "Investigations with 2+ linked requests", 6, 34),
            SignalSpec("practice", "Contextual access-control practice", 6, 18),
        ),
    ),
    SkillSpec(
        key="authentication",
        label="Authentication",
        blurb="Reviewing login, session, MFA, and recovery flows.",
        next_step="Open the Auth Flow Analyzer and walk each observed stage's manual-review checks.",
        signals=(
            SignalSpec("auth_flow_stages", "Auth-flow stages observed", 6, 42),
            SignalSpec("auth_investigations", "Investigations into auth behavior", 9, 33),
            SignalSpec("practice", "Contextual authentication practice", 6, 18),
        ),
    ),
    SkillSpec(
        key="reporting",
        label="Reporting",
        blurb="Validating a finding and writing it up so it stands on its own.",
        next_step="Work an investigation through the false-positive checklist, attach evidence, and generate its report.",
        signals=(
            SignalSpec("validated_findings", "Findings validated", 14, 42),
            SignalSpec("reports", "Reports drafted", 9, 27),
            SignalSpec("full_fp_checklists", "False-positive checklists fully worked", 5, 20),
            SignalSpec("evidence_files", "Evidence files attached", 2, 15),
        ),
    ),
)

SKILL_BY_KEY = {spec.key: spec for spec in SKILLS}

# Which skill each contextual practice lab feeds (Section 29-30: practice a
# concept, and it counts toward the skill it teaches).
LAB_SKILL: dict[str, str] = {
    "idor": "access_control",
    "cors": "http",
    "cookies": "authentication",
    "headers": "http",
    "info-exposure": "api_analysis",
}

_BANDS = (
    (0, "not started"),
    (1, "getting started"),
    (25, "developing"),
    (50, "proficient"),
    (75, "strong"),
)


def band_for(score: int) -> str:
    label = "not started"
    for threshold, name in _BANDS:
        if score >= threshold:
            label = name
    return label


def score_skill(spec: SkillSpec, counts: dict[str, int]) -> dict:
    contributing: list[dict] = []
    score = 0
    for signal in spec.signals:
        count = int(counts.get(signal.key, 0) or 0)
        if count <= 0:
            continue
        points = min(signal.cap, count * signal.points_each)
        score += points
        contributing.append({"label": signal.label, "count": count, "points": points})
    score = min(100, score)
    return {
        "key": spec.key,
        "label": spec.label,
        "blurb": spec.blurb,
        "score": score,
        "level": round(score / 10),
        "band": band_for(score),
        "signals": contributing,
        "next_step": spec.next_step,
    }
