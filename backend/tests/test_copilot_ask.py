import asyncio

import anthropic
import httpx2

import app.copilot.anthropic_provider as anthropic_provider_module
from app.copilot.knowledge import _fallback_message, ask_hunt_copilot
from app.copilot.router import _build_ask_context
from app.copilot.schemas import AskRequest
from app.http.models import HttpTransaction


class _FakeDb:
    def __init__(self, objects: dict):
        self._objects = objects

    def get(self, model, obj_id):
        return self._objects.get((model, obj_id))


def test_build_ask_context_masks_request_and_response_secrets():
    tx = HttpTransaction(
        id=1,
        project_id=1,
        method="GET",
        url="https://api.example.com/",
        request_headers={"Authorization": "Bearer super-secret-real-token"},
        request_body=None,
        status_code=200,
        response_headers={"Set-Cookie": "session=abc123456789"},
        response_cookies=["session=abc123456789; Path=/"],
        response_body='{"password": "hunter2verysecret"}',
        response_body_truncated=False,
        response_size_bytes=10,
        timing_ms=1.0,
        technologies=[],
        interesting_indicators=[],
        error=None,
    )
    db = _FakeDb({(HttpTransaction, 1): tx})

    context = _build_ask_context(db, project_id=1, payload=AskRequest(question="q", transaction_id=1))

    assert "super-secret-real-token" not in str(context)
    assert "abc123456789" not in str(context)
    assert "hunter2verysecret" not in str(context)


def test_build_ask_context_ignores_entities_from_a_different_project():
    tx = HttpTransaction(
        id=1, project_id=2, method="GET", url="https://api.example.com/", request_headers={}, request_body=None,
        status_code=200, response_headers={}, response_cookies=[], response_body=None,
        response_body_truncated=False, response_size_bytes=0, timing_ms=1.0, technologies=[],
        interesting_indicators=[], error=None,
    )
    db = _FakeDb({(HttpTransaction, 1): tx})

    context = _build_ask_context(db, project_id=1, payload=AskRequest(question="q", transaction_id=1))

    assert context == {}


def _fake_response(status_code: int) -> httpx2.Response:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return httpx2.Response(status_code, request=request)


class _FakeSucceedingProvider:
    name = "anthropic"

    async def ask(self, question: str, context: dict) -> str:
        return f"answered: {question} with context keys {sorted(context.keys())}"


class _FakeFailingProvider:
    name = "anthropic"

    def __init__(self, exc: Exception):
        self._exc = exc

    async def ask(self, question: str, context: dict) -> str:
        raise self._exc


def test_ask_hunt_copilot_uses_live_provider_when_it_succeeds(monkeypatch):
    monkeypatch.setattr(anthropic_provider_module, "AnthropicProvider", _FakeSucceedingProvider)

    answer, provider = asyncio.run(ask_hunt_copilot("What should I check next?", {"asset_hostname": "api.example.com"}))

    assert provider == "anthropic"
    assert "What should I check next?" in answer
    assert "asset_hostname" in answer


def test_ask_hunt_copilot_falls_back_to_rule_based_on_generic_failure(monkeypatch):
    monkeypatch.setattr(
        anthropic_provider_module, "AnthropicProvider", lambda: _FakeFailingProvider(RuntimeError("boom"))
    )

    answer, provider = asyncio.run(ask_hunt_copilot("Explain this cookie", {}))

    assert provider == "rule_based"
    assert "unexpected error" in answer.lower()


def test_fallback_message_for_no_credentials_configured_at_all():
    """The most common real case: no ANTHROPIC_API_KEY / auth token / profile
    at all. Confirmed live that the SDK raises a plain TypeError with this
    message client-side, before any network call - not AuthenticationError,
    which is reserved for a real 401 (a *bad* key, not a *missing* one)."""
    exc = TypeError(
        "Could not resolve authentication method. Expected one of api_key, auth_token, or "
        "credentials to be set. Or for one of the `X-Api-Key` or `Authorization` headers to be "
        "explicitly omitted"
    )
    msg = asyncio.run(_fallback_message(exc))
    assert "ANTHROPIC_API_KEY" in msg


def test_fallback_message_for_unrelated_type_error_is_not_misclassified():
    msg = asyncio.run(_fallback_message(TypeError("unrelated type error")))
    assert "ANTHROPIC_API_KEY" not in msg
    assert "unexpected error" in msg.lower()


def test_fallback_message_for_authentication_error():
    exc = anthropic.AuthenticationError("bad key", response=_fake_response(401), body=None)
    msg = asyncio.run(_fallback_message(exc))
    assert "ANTHROPIC_API_KEY" in msg


def test_fallback_message_for_rate_limit_error():
    exc = anthropic.RateLimitError("slow down", response=_fake_response(429), body=None)
    msg = asyncio.run(_fallback_message(exc))
    assert "rate-limited" in msg.lower()


def test_fallback_message_for_connection_error():
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    exc = anthropic.APIConnectionError(request=request)
    msg = asyncio.run(_fallback_message(exc))
    assert "network error" in msg.lower()
