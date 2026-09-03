from app.practice import labs
from app.practice.router import router
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_cors_lab_supports_browser_safe_practice_origin():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.get("/api/practice/cors/me", headers={"X-Practice-Origin": "https://evil.example"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://evil.example"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_resolve_practice_identity_valid_tokens():
    assert labs.resolve_practice_identity("Bearer practice-token-alice") == "alice"
    assert labs.resolve_practice_identity("Bearer practice-token-bob") == "bob"


def test_resolve_practice_identity_rejects_unknown_or_missing_token():
    assert labs.resolve_practice_identity("Bearer not-a-real-token") is None
    assert labs.resolve_practice_identity("") is None


def test_get_fake_order_returns_order_regardless_of_owner():
    """This IS the vulnerability the lab exists to teach - the function
    itself does no ownership check. The router layer deliberately doesn't
    either; that's the concept, not a bug in this test."""
    alice_order = labs.get_fake_order(1)
    bob_order = labs.get_fake_order(3)

    assert alice_order["owner"] == "alice"
    assert bob_order["owner"] == "bob"
    # Both are retrievable via the same lookup with no identity check at all.
    assert labs.get_fake_order(1) is not None
    assert labs.get_fake_order(3) is not None


def test_get_fake_order_missing_id_returns_none():
    assert labs.get_fake_order(999) is None


def test_catalog_has_unique_ids_and_required_fields():
    ids = [lab.id for lab in labs.CATALOG]
    assert len(ids) == len(set(ids))
    for lab in labs.CATALOG:
        assert lab.title
        assert lab.mini_lesson_title
        assert lab.mini_lesson
        assert lab.try_it_steps
        assert lab.title_te
        assert lab.mini_lesson_title_te
        assert lab.mini_lesson_te
        assert lab.try_it_steps_te
        assert len(lab.try_it_steps_te) == len(lab.try_it_steps)


def test_catalog_api_exposes_bilingual_learning_content():
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/api/practice/labs/idor")
    assert response.status_code == 200
    content = response.json()
    assert content["title"]
    assert content["title_te"]
    assert content["try_it_steps_te"]


def test_catalog_by_id_matches_catalog():
    for lab in labs.CATALOG:
        assert labs.CATALOG_BY_ID[lab.id] is lab
