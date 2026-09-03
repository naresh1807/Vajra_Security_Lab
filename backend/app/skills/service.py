"""
Vajra Personal Bug Bounty Skill Map (Sections 39, 40) - computed per user.

Aggregates real activity across every project the user owns and feeds it
to the pure scorer. Nothing is stored; the map is recomputed on read, so
it always reflects what the hunter has actually done.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api_mapper.categorize import normalize_path
from app.authflow.stages import assign_stage
from app.evidence.models import EvidenceAttachment
from app.diff.models import AccessControlScenario
from app.http.models import HttpTransaction
from app.investigations.models import FALSE_POSITIVE_QUESTIONS, Investigation, InvestigationSource, InvestigationStatus
from app.js_inspector.models import FindingType, JsFile, JsFinding
from app.projects.models import Project
from app.recon.models import Asset, ReconJob, ReconJobStatus
from app.reports.models import Report
from app.skills.scoring import LAB_SKILL, SKILLS, score_skill
from app.surface.models import DiscoveredEndpoint

_AUTH_KEYWORDS = (
    "login", "logout", "log in", "sign in", "signin", "auth", "session", "password",
    "reset", "mfa", "2fa", "otp", "oauth", "token", "sso", "register", "verification",
    "credential",
)


def _empty_counts() -> dict[str, dict[str, int]]:
    return {spec.key: {} for spec in SKILLS}


def build_skill_map(db: Session, user_id: int) -> dict:
    project_ids = [pid for (pid,) in db.query(Project.id).filter(Project.owner_id == user_id)]
    counts = _empty_counts()

    activity = {
        "projects": len(project_ids),
        "recon_jobs": 0,
        "http_requests": 0,
        "endpoint_shapes": 0,
        "js_files": 0,
        "investigations": 0,
        "findings": 0,
        "reports": 0,
        "evidence_files": 0,
        "labs_completed": 0,
    }

    if project_ids:
        _recon(db, project_ids, counts, activity)
        _http(db, project_ids, counts, activity)
        _api(db, project_ids, counts, activity)
        _access_control(db, project_ids, counts, activity)
        _authentication(db, project_ids, counts, activity)
        _reporting(db, project_ids, counts, activity)
        _practice(db, project_ids, counts, activity)

    skills = [score_skill(spec, counts[spec.key]) for spec in SKILLS]
    strengths = [s["label"] for s in skills if s["score"] >= 60]
    growth_areas = [s["label"] for s in skills if 0 < s["score"] < 35]
    not_started = [s["label"] for s in skills if s["score"] == 0]

    if not any(s["score"] for s in skills):
        headline = "No hunting activity yet - your skill map fills in as you work through real projects."
    else:
        parts = []
        if strengths:
            parts.append("Strong: " + ", ".join(strengths))
        weak = growth_areas + not_started
        if weak:
            parts.append("Needs more practice: " + ", ".join(weak[:3]))
        headline = " · ".join(parts) or "Keep going - every skill is developing."

    return {
        "skills": skills,
        "activity": activity,
        "strengths": strengths,
        "growth_areas": growth_areas + not_started,
        "headline": headline,
        "note": (
            "Every score is computed from real actions in your projects (Section 39) - there are no quizzes "
            "and no course to complete. Open a skill to see exactly which activity produced its score."
        ),
    }


def _recon(db, project_ids, counts, activity):
    completed = (
        db.query(func.count(ReconJob.id))
        .filter(ReconJob.project_id.in_(project_ids), ReconJob.status == ReconJobStatus.COMPLETED)
        .scalar()
    ) or 0
    live = (
        db.query(func.count(Asset.id))
        .filter(Asset.project_id.in_(project_ids), Asset.is_live.is_(True))
        .scalar()
    ) or 0
    projects_with_surface = (
        db.query(func.count(func.distinct(Asset.project_id)))
        .filter(Asset.project_id.in_(project_ids))
        .scalar()
    ) or 0
    counts["recon"] = {
        "completed_recon_jobs": completed,
        "live_hosts": live,
        "projects_with_surface": projects_with_surface,
    }
    activity["recon_jobs"] = completed


def _http(db, project_ids, counts, activity):
    transactions = db.query(HttpTransaction).filter(HttpTransaction.project_id.in_(project_ids)).all()
    patterns = {normalize_path(urlsplit(tx.url).path or "/") for tx in transactions}
    with_identity = sum(1 for tx in transactions if tx.identity_profile_key)
    counts["http"] = {
        "http_requests": len(transactions),
        "distinct_endpoint_patterns": len(patterns),
        "requests_with_identity": with_identity,
    }
    activity["http_requests"] = len(transactions)
    activity["endpoint_shapes"] = len(patterns)


def _api(db, project_ids, counts, activity):
    js_files = db.query(func.count(JsFile.id)).filter(JsFile.project_id.in_(project_ids)).scalar() or 0
    endpoints = (
        db.query(func.count(DiscoveredEndpoint.id))
        .filter(DiscoveredEndpoint.project_id.in_(project_ids))
        .scalar()
    ) or 0
    api_routes = (
        db.query(func.count(JsFinding.id))
        .join(JsFile, JsFinding.js_file_id == JsFile.id)
        .filter(JsFile.project_id.in_(project_ids), JsFinding.finding_type == FindingType.API_ROUTE)
        .scalar()
    ) or 0
    counts["api_analysis"] = {
        "js_files": js_files,
        "discovered_endpoints": endpoints,
        "js_api_routes": api_routes,
    }
    activity["js_files"] = js_files


def _access_control(db, project_ids, counts, activity):
    scenarios = (
        db.query(func.count(AccessControlScenario.id))
        .filter(AccessControlScenario.project_id.in_(project_ids))
        .scalar()
    ) or 0
    investigations = db.query(Investigation).filter(Investigation.project_id.in_(project_ids)).all()
    diff_investigations = sum(1 for inv in investigations if inv.source == InvestigationSource.DIFF_RESULT)
    multi_request = sum(1 for inv in investigations if len(inv.linked_transaction_ids or []) >= 2)
    counts["access_control"] = {
        "scenarios": scenarios,
        "diff_investigations": diff_investigations,
        "multi_request_investigations": multi_request,
    }


def _authentication(db, project_ids, counts, activity):
    stages: set[str] = set()
    for tx in db.query(HttpTransaction).filter(HttpTransaction.project_id.in_(project_ids)):
        stage = assign_stage(tx.method, urlsplit(tx.url).path or "/")
        if stage:
            stages.add(stage)
    for endpoint in db.query(DiscoveredEndpoint).filter(DiscoveredEndpoint.project_id.in_(project_ids)):
        stage = assign_stage(endpoint.method, endpoint.path)
        if stage:
            stages.add(stage)

    auth_investigations = 0
    for inv in db.query(Investigation).filter(Investigation.project_id.in_(project_ids)):
        haystack = " ".join(
            [inv.title or "", inv.endpoint or "", inv.notes or "", inv.ai_notes or ""]
        ).lower()
        if any(keyword in haystack for keyword in _AUTH_KEYWORDS):
            auth_investigations += 1

    counts["authentication"] = {
        "auth_flow_stages": len(stages),
        "auth_investigations": auth_investigations,
    }


def _reporting(db, project_ids, counts, activity):
    investigations = db.query(Investigation).filter(Investigation.project_id.in_(project_ids)).all()
    validated = sum(1 for inv in investigations if inv.status == InvestigationStatus.VALIDATED)
    full_checklists = sum(
        1
        for inv in investigations
        if inv.false_positive_checklist
        and all(inv.false_positive_checklist.get(key) is not None for key in FALSE_POSITIVE_QUESTIONS)
    )
    reports = (
        db.query(func.count(Report.id))
        .join(Investigation, Report.investigation_id == Investigation.id)
        .filter(Investigation.project_id.in_(project_ids))
        .scalar()
    ) or 0
    evidence = (
        db.query(func.count(EvidenceAttachment.id))
        .join(Investigation, EvidenceAttachment.investigation_id == Investigation.id)
        .filter(Investigation.project_id.in_(project_ids))
        .scalar()
    ) or 0
    counts["reporting"] = {
        "validated_findings": validated,
        "reports": reports,
        "full_fp_checklists": full_checklists,
        "evidence_files": evidence,
    }
    activity["investigations"] = len(investigations)
    activity["findings"] = validated
    activity["reports"] = reports
    activity["evidence_files"] = evidence


def _practice(db, project_ids, counts, activity):
    """A started lab counts 1, a completed lab counts 2, toward the skill it teaches."""
    per_skill: dict[str, dict[str, str]] = {}
    for inv in db.query(Investigation).filter(Investigation.project_id.in_(project_ids)):
        for lab_id, status in (inv.practice_progress or {}).items():
            skill = LAB_SKILL.get(lab_id)
            if not skill:
                continue
            existing = per_skill.setdefault(skill, {}).get(lab_id)
            # completed beats started if the same lab appears on two investigations
            if existing != "completed":
                per_skill[skill][lab_id] = status

    completed_total = 0
    for skill, labs in per_skill.items():
        practice_count = sum(2 if status == "completed" else 1 for status in labs.values())
        completed_total += sum(1 for status in labs.values() if status == "completed")
        counts[skill]["practice"] = counts[skill].get("practice", 0) + practice_count
    activity["labs_completed"] = completed_total
