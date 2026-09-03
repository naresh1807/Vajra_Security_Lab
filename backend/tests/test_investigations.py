from datetime import datetime, timezone

from app.investigations.models import Investigation, InvestigationSource, InvestigationStatus
from app.investigations.service import compute_false_positive_hint, compute_missing_evidence, recommended_practice_labs, to_out


def _investigation(**overrides) -> Investigation:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=1,
        project_id=1,
        title="Potential API Authorization Issue",
        target="api.example.com",
        endpoint="GET /api/orders/{id}",
        status=InvestigationStatus.OPEN,
        source=InvestigationSource.MANUAL,
        source_reference={},
        ai_notes="",
        confidence=0,
        linked_transaction_ids=[],
        linked_asset_id=None,
        notes="",
        false_positive_checklist={},
        impact_observed="",
        impact_potential="",
        practice_progress={},
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return Investigation(**defaults)


def test_missing_evidence_lists_everything_absent_on_a_fresh_investigation():
    inv = _investigation()
    missing = compute_missing_evidence(inv)

    assert any("No evidence" in m for m in missing)
    assert any("6 of 6 false-positive checks" in m for m in missing)
    assert any("Observed impact" in m for m in missing)
    assert any("No investigation notes" in m for m in missing)


def test_missing_evidence_shrinks_as_investigation_fills_in():
    inv = _investigation(
        linked_transaction_ids=[1, 2],
        false_positive_checklist={"authentication_required": True, "reproducible": True},
        impact_observed="Order data belonging to another account was returned.",
        notes="Sent two requests with different tokens and compared responses.",
    )
    missing = compute_missing_evidence(inv)

    assert not any("No evidence" in m for m in missing)
    assert any("4 of 6 false-positive checks" in m for m in missing)
    assert not any("Observed impact" in m for m in missing)
    assert not any("No investigation notes" in m for m in missing)


def test_false_positive_hint_when_program_excludes_issue():
    hint = compute_false_positive_hint({"program_excludes_issue": True})
    assert hint is not None
    assert "excludes this issue" in hint


def test_false_positive_hint_when_behavior_intended():
    hint = compute_false_positive_hint({"behavior_intended": True})
    assert "intended" in hint


def test_false_positive_hint_none_when_signals_point_to_a_real_finding():
    hint = compute_false_positive_hint(
        {
            "program_excludes_issue": False,
            "behavior_intended": False,
            "object_belongs_to_other_account": True,
            "reproducible": True,
        }
    )
    assert hint is None


def test_to_out_includes_computed_fields_and_static_question_text():
    inv = _investigation()
    out = to_out(inv)

    assert out.missing_evidence  # non-empty on a fresh investigation
    assert "object_belongs_to_other_account" in out.false_positive_questions
    assert out.false_positive_questions["object_belongs_to_other_account"] == "Does the object belong to another controlled account?"
    assert out.recommended_practice_labs == ["idor"]


def test_practice_recommendations_follow_investigation_context():
    inv = _investigation(title="Credentialed CORS origin reflection", notes="Session cookie also lacks SameSite")
    assert recommended_practice_labs(inv) == ["cors", "cookies"]


def test_to_out_preserves_practice_progress():
    inv = _investigation(practice_progress={"idor": "completed"})
    assert to_out(inv).practice_progress == {"idor": "completed"}
