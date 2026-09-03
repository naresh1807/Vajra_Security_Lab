from datetime import datetime, timezone

from app.evidence.schemas import MaskedTransactionOut
from app.investigations.models import Investigation, InvestigationSource, InvestigationStatus
from app.reports.service import compute_readiness, generate_steps_to_reproduce, seed_report, suggest_remediation


def _investigation(**overrides) -> Investigation:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=1,
        project_id=1,
        title="Potential Broken Object Authorization on /orders/{id}",
        target="api.example.com",
        endpoint="GET /api/orders/{id}",
        status=InvestigationStatus.OPEN,
        source=InvestigationSource.DIFF_RESULT,
        source_reference={},
        ai_notes="Object identifier detected; different sessions returned similarly-shaped data.",
        confidence=70,
        linked_transaction_ids=[1, 2],
        linked_asset_id=None,
        notes="",
        false_positive_checklist={},
        impact_observed="",
        impact_potential="",
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return Investigation(**defaults)


def _masked_tx(**overrides) -> MaskedTransactionOut:
    defaults = dict(
        id=1,
        method="GET",
        url="https://api.example.com/orders/1",
        request_headers={"Authorization": "Bear****oken"},
        request_body=None,
        status_code=200,
        response_headers={},
        response_cookies=[],
        response_body=None,
        created_at=datetime.now(timezone.utc),
        masking_verifiable=True,
    )
    defaults.update(overrides)
    return MaskedTransactionOut(**defaults)


def test_generate_steps_to_reproduce_numbers_each_request_with_identity_and_status():
    txs = [
        _masked_tx(id=1, url="https://api.example.com/orders/1", request_headers={"Authorization": "Bear****oken"}),
        _masked_tx(id=2, url="https://api.example.com/orders/2", request_headers={"Authorization": "Bear****ther"}, status_code=200),
    ]
    steps = generate_steps_to_reproduce(txs)

    assert "1. Send GET https://api.example.com/orders/1 using Bear****oken." in steps
    assert "2. Send GET https://api.example.com/orders/2 using Bear****ther." in steps
    assert "Observed: HTTP 200." in steps


def test_generate_steps_to_reproduce_empty_when_no_transactions():
    assert generate_steps_to_reproduce([]) == ""


def test_generate_steps_names_controlled_identity_without_exposing_header_value():
    steps = generate_steps_to_reproduce([
        _masked_tx(identity_profile_name="Account A", request_headers={"Authorization": "Bear****oken"})
    ])

    assert "using controlled identity 'Account A'" in steps
    assert "Bear****oken" not in steps


def test_suggest_remediation_uses_analyzer_category_hint():
    inv = _investigation(source=InvestigationSource.ANALYZER_FINDING, source_reference={"category": "cors"})
    hint = suggest_remediation(inv)
    assert "Origin" in hint and "allowlist" in hint


def test_suggest_remediation_falls_back_to_diff_hint():
    inv = _investigation(source=InvestigationSource.DIFF_RESULT, source_reference={})
    hint = suggest_remediation(inv)
    assert "ownership" in hint


def test_seed_report_pulls_from_investigation_and_generated_steps():
    inv = _investigation()
    txs = [_masked_tx()]
    seeded = seed_report(inv, txs)

    assert seeded["summary"] == inv.ai_notes
    assert "1. Send GET" in seeded["steps_to_reproduce"]
    assert seeded["suggested_remediation"]  # diff_result hint


def test_seed_report_includes_preserved_scenario_prerequisites():
    inv = _investigation(access_control_snapshot={
        "warnings": ["All available requests use the same identity."],
        "selected_cells": [{"identity_a": "Account A", "identity_b": "Account B"}],
    })

    seeded = seed_report(inv, [_masked_tx(identity_profile_name="Account A")])

    assert seeded["prerequisites"] == (
        "Controlled test identities: Account A, Account B. "
        "Review the preserved scenario setup warnings before treating the comparison as valid."
    )


def test_compute_readiness_full_score_when_everything_checked():
    inv = _investigation(
        impact_observed="Bob's token retrieved Alice's order data.",
        false_positive_checklist={"reproducible": True, "program_excludes_issue": False},
    )
    result = compute_readiness(inv, has_evidence_attachment=True, scope_verified=True)

    assert result.score == 100
    assert result.missing == []


def test_compute_readiness_reports_missing_items_honestly():
    inv = _investigation(
        title="short",
        impact_observed="",
        linked_transaction_ids=[],
        false_positive_checklist={},
    )
    result = compute_readiness(inv, has_evidence_attachment=False, scope_verified=False)

    assert result.score < 100
    assert "At least one screenshot attached" in result.missing
    assert "Scope verified for this target" in result.missing
    assert "Sensitive information masked in evidence" not in result.missing  # always passes
