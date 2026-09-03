import json

from app.diff.service import compare_transactions
from app.http.models import HttpTransaction


def _tx(**overrides) -> HttpTransaction:
    defaults = dict(
        id=1,
        project_id=1,
        method="GET",
        url="https://api.example.com/orders/1",
        request_headers={},
        request_body=None,
        status_code=200,
        response_headers={"content-type": "application/json"},
        response_cookies=[],
        response_body=json.dumps({"id": 1, "owner": "alice", "total": 42}),
        response_body_truncated=False,
        response_size_bytes=40,
        timing_ms=10.0,
        technologies=[],
        interesting_indicators=[],
        error=None,
    )
    defaults.update(overrides)
    return HttpTransaction(**defaults)


def test_same_identity_different_object_is_inconclusive_but_not_zero_evidence():
    tx_a = _tx(id=1, url="https://api.example.com/orders/1", request_headers={"Authorization": "Bearer X"})
    tx_b = _tx(id=2, url="https://api.example.com/orders/2", request_headers={"Authorization": "Bearer X"})

    result = compare_transactions(tx_a, tx_b)

    assert result.same_identity is True
    assert result.same_endpoint_pattern is True
    assert result.finding.category == "Inconclusive - same identity used"
    assert any("same identity" in n for n in result.finding.notes)


def test_distinct_controlled_profiles_override_matching_header_values():
    common = {"Authorization": "Bearer same-placeholder"}
    tx_a = _tx(id=1, identity_profile_key="profile-a", identity_profile_name="Account A", request_headers=common)
    tx_b = _tx(
        id=2,
        url="https://api.example.com/orders/2",
        identity_profile_key="profile-b",
        identity_profile_name="Account B",
        request_headers=common,
    )

    result = compare_transactions(tx_a, tx_b)

    assert result.same_identity is False
    assert result.identity_a == "Account A"
    assert result.identity_b == "Account B"
    assert result.identity_basis == "controlled profiles"


def test_matching_controlled_profile_key_is_same_identity():
    tx_a = _tx(id=1, identity_profile_key="profile-a", identity_profile_name="Account A")
    tx_b = _tx(id=2, url="https://api.example.com/orders/2", identity_profile_key="profile-a", identity_profile_name="Account A")

    result = compare_transactions(tx_a, tx_b)

    assert result.same_identity is True
    assert result.identity_basis == "controlled profiles"


def test_different_identity_both_success_similar_shape_is_potential_finding():
    tx_a = _tx(
        id=1,
        url="https://api.example.com/orders/1",
        request_headers={"Authorization": "Bearer alice-token"},
        response_body=json.dumps({"id": 1, "owner": "alice", "total": 42}),
        response_size_bytes=40,
    )
    tx_b = _tx(
        id=2,
        url="https://api.example.com/orders/2",
        request_headers={"Authorization": "Bearer bob-token"},
        response_body=json.dumps({"id": 2, "owner": "bob", "total": 55}),
        response_size_bytes=39,
    )

    result = compare_transactions(tx_a, tx_b)

    assert result.same_identity is False
    assert result.finding.category == "Potential Broken Object Authorization"
    assert result.finding.confidence >= 60


def test_different_endpoint_shapes_are_not_comparable():
    tx_a = _tx(id=1, url="https://api.example.com/orders/1")
    tx_b = _tx(id=2, url="https://api.example.com/users/1")

    result = compare_transactions(tx_a, tx_b)

    assert result.same_endpoint_pattern is False
    assert result.finding.category == "Not directly comparable"
    assert result.finding.confidence == 0


def test_failed_transaction_is_not_comparable():
    tx_a = _tx(id=1, error="ConnectTimeout: the request did not complete.", status_code=None)
    tx_b = _tx(id=2)

    result = compare_transactions(tx_a, tx_b)

    assert result.finding.category == "Not comparable"
    assert result.finding.confidence == 0


def test_body_key_diff_reports_keys_unique_to_each_side():
    tx_a = _tx(id=1, response_body=json.dumps({"id": 1, "owner": "alice"}))
    tx_b = _tx(id=2, url="https://api.example.com/orders/2", response_body=json.dumps({"id": 2, "admin_notes": "x"}))

    result = compare_transactions(tx_a, tx_b)

    assert "owner" in result.body_keys_only_in_a
    assert "admin_notes" in result.body_keys_only_in_b
    assert "id" in result.body_common_keys
