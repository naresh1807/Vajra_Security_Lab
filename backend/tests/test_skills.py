"""
Vajra Personal Bug Bounty Skill Map (Sections 39, 40).

The pure scorer (signals -> capped score -> band), then the computed map
deriving those signals from real activity across a user's projects -
and staying empty and honest when there's been none.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.database import Base
from app.diff.models import AccessControlScenario
from app.http.models import HttpTransaction
from app.investigations.models import Investigation, InvestigationSource, InvestigationStatus
from app.projects.models import Project
from app.recon.models import Asset, ReconJob, ReconJobStatus
from app.reports.models import Report
from app.skills.scoring import SKILL_BY_KEY, band_for, score_skill
from app.skills.service import build_skill_map


# --- pure scorer --------------------------------------------------------

def test_band_thresholds():
    assert band_for(0) == "not started"
    assert band_for(1) == "getting started"
    assert band_for(25) == "developing"
    assert band_for(50) == "proficient"
    assert band_for(75) == "strong"


def test_score_is_capped_per_signal_and_overall():
    recon = SKILL_BY_KEY["recon"]
    # 100 recon jobs would be 700 points uncapped; the signal caps at 42.
    result = score_skill(recon, {"completed_recon_jobs": 100})
    assert result["score"] == 42
    assert result["signals"][0]["count"] == 100
    assert result["signals"][0]["points"] == 42


def test_zero_count_signals_are_omitted_from_the_breakdown():
    result = score_skill(SKILL_BY_KEY["http"], {"http_requests": 2})
    assert [s["label"] for s in result["signals"]] == ["Requests sent"]
    assert result["score"] == 6


# --- computed map -------------------------------------------------------

def _seed_user_with_project(db: Session) -> tuple[int, int]:
    user = User(email="hunter@example.com", password_hash="x")
    db.add(user)
    db.flush()
    project = Project(
        name="P", target="example.com", allowed_domains=["example.com"],
        allowed_subdomains=[], excluded_assets=[], rate_limit_rps=1.0, owner_id=user.id,
    )
    db.add(project)
    db.flush()
    return user.id, project.id


def test_empty_map_is_all_zero_and_says_so():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(email="new@example.com", password_hash="x")
        db.add(user)
        db.commit()
        result = build_skill_map(db, user.id)

    assert [s["key"] for s in result["skills"]] == [
        "recon", "http", "api_analysis", "access_control", "authentication", "reporting"
    ]
    assert all(s["score"] == 0 and s["band"] == "not started" for s in result["skills"])
    assert result["strengths"] == []
    assert "No hunting activity yet" in result["headline"]


def test_map_derives_scores_from_real_activity():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user_id, project_id = _seed_user_with_project(db)

        for _ in range(3):
            db.add(ReconJob(project_id=project_id, status=ReconJobStatus.COMPLETED))
        for i in range(5):
            db.add(Asset(project_id=project_id, hostname=f"h{i}.example.com", is_live=True, source="dns"))
        for i in range(6):
            db.add(HttpTransaction(
                project_id=project_id, method="GET",
                url=f"https://api.example.com/api/orders/{i}",
                identity_profile_key="alice" if i % 2 else None,
            ))
        db.add(AccessControlScenario(project_id=project_id, name="s1", transaction_ids=[1, 2]))
        inv = Investigation(
            project_id=project_id, title="Broken auth on login", status=InvestigationStatus.VALIDATED,
            source=InvestigationSource.DIFF_RESULT, linked_transaction_ids=[1, 2],
        )
        db.add(inv)
        db.flush()
        db.add(Report(investigation_id=inv.id, summary="x"))
        db.commit()

        result = build_skill_map(db, user_id)

    skills = {s["key"]: s for s in result["skills"]}

    assert skills["recon"]["score"] > 0
    assert skills["http"]["score"] > 0
    # 6 requests -> one endpoint shape (/api/orders/{id}); 3 sent as an identity.
    http_signals = {s["label"]: s["count"] for s in skills["http"]["signals"]}
    assert http_signals["Requests sent"] == 6
    assert http_signals["Distinct endpoint shapes exercised"] == 1
    assert http_signals["Requests sent as a controlled identity"] == 3

    assert skills["access_control"]["score"] > 0  # scenario + diff investigation + 2 linked txns
    assert skills["authentication"]["signals"]  # "login" investigation + /login isn't present, but title matches
    assert skills["reporting"]["score"] > 0  # 1 validated finding + 1 report

    assert result["activity"]["http_requests"] == 6
    assert result["activity"]["findings"] == 1
    assert result["activity"]["reports"] == 1


def test_map_is_scoped_to_the_requesting_user():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        mine_id, my_project = _seed_user_with_project(db)
        other = User(email="other@example.com", password_hash="x")
        db.add(other)
        db.flush()
        their_project = Project(
            name="Theirs", target="other.com", allowed_domains=["other.com"],
            allowed_subdomains=[], excluded_assets=[], rate_limit_rps=1.0, owner_id=other.id,
        )
        db.add(their_project)
        db.flush()
        for _ in range(5):
            db.add(ReconJob(project_id=their_project.id, status=ReconJobStatus.COMPLETED))
        db.commit()

        mine = build_skill_map(db, mine_id)

    assert all(s["score"] == 0 for s in mine["skills"])  # their recon doesn't count for me
