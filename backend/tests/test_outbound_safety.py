import asyncio

import httpx
import pytest

from app.core import outbound
from app.core.outbound import OutboundSafetyError, request_with_safe_redirects, validate_outbound_url
from app.projects.models import Project


def _project(**overrides) -> Project:
    values = {
        "name": "Test",
        "target": "example.com",
        "allowed_domains": ["example.com"],
        "allowed_subdomains": [],
        "excluded_assets": [],
        "rate_limit_rps": 10.0,
    }
    values.update(overrides)
    return Project(**values)


def test_rejects_non_http_scheme():
    with pytest.raises(OutboundSafetyError, match="HTTP and HTTPS"):
        asyncio.run(validate_outbound_url(_project(), "file:///etc/passwd"))


def test_rejects_embedded_url_credentials(monkeypatch):
    monkeypatch.setattr(outbound, "_resolve_addresses", lambda host: {"93.184.216.34"})
    with pytest.raises(OutboundSafetyError, match="Credentials embedded"):
        asyncio.run(validate_outbound_url(_project(), "https://user:pass@example.com/private"))


def test_rejects_private_dns_answer(monkeypatch):
    monkeypatch.setattr(outbound, "_resolve_addresses", lambda host: {"127.0.0.1"})
    with pytest.raises(OutboundSafetyError, match="non-public address"):
        asyncio.run(validate_outbound_url(_project(), "https://example.com/"))


def test_rejects_out_of_scope_redirect_before_following(monkeypatch):
    monkeypatch.setattr(outbound, "_resolve_addresses", lambda host: {"93.184.216.34"})
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(302, headers={"Location": "https://evil.org/private"}, request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await request_with_safe_redirects(client, _project(), "GET", "https://example.com/start")

    with pytest.raises(OutboundSafetyError, match="ScopeGuard blocked"):
        asyncio.run(run())
    assert calls == ["https://example.com/start"]


def test_cross_origin_in_scope_redirect_strips_credentials(monkeypatch):
    monkeypatch.setattr(outbound, "_resolve_addresses", lambda host: {"93.184.216.34"})
    seen_authorization: list[str | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_authorization.append(request.headers.get("authorization"))
        if request.url.host == "example.com":
            return httpx.Response(302, headers={"Location": "https://api.example.com/end"}, request=request)
        return httpx.Response(200, text="ok", request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await request_with_safe_redirects(
                client, _project(), "GET", "https://example.com/start", headers={"Authorization": "Bearer secret"}
            )

    response = asyncio.run(run())
    assert response.status_code == 200
    assert seen_authorization == ["Bearer secret", None]


def test_cross_origin_redirect_strips_custom_identity_headers(monkeypatch):
    monkeypatch.setattr(outbound, "_resolve_addresses", lambda host: {"93.184.216.34"})
    seen_keys: list[str | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_keys.append(request.headers.get("x-api-key"))
        if request.url.host == "example.com":
            return httpx.Response(302, headers={"Location": "https://api.example.com/end"}, request=request)
        return httpx.Response(200, text="ok", request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await request_with_safe_redirects(
                client,
                _project(),
                "GET",
                "https://example.com/start",
                headers={"X-API-Key": "stored-secret"},
                sensitive_header_names={"X-API-Key"},
            )

    response = asyncio.run(run())
    assert response.status_code == 200
    assert seen_keys == ["stored-secret", None]


def test_https_to_http_redirect_is_cross_origin_for_credentials(monkeypatch):
    monkeypatch.setattr(outbound, "_resolve_addresses", lambda host: {"93.184.216.34"})
    seen_authorization: list[str | None] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_authorization.append(request.headers.get("authorization"))
        if request.url.scheme == "https":
            return httpx.Response(302, headers={"Location": "http://example.com/end"}, request=request)
        return httpx.Response(200, text="ok", request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await request_with_safe_redirects(
                client,
                _project(),
                "GET",
                "https://example.com/start",
                headers={"Authorization": "Bearer secret"},
            )

    response = asyncio.run(run())
    assert response.status_code == 200
    assert seen_authorization == ["Bearer secret", None]


def test_bounded_response_stops_oversized_metadata_download(monkeypatch):
    monkeypatch.setattr(outbound, "_resolve_addresses", lambda host: {"93.184.216.34"})

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 20, request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await request_with_safe_redirects(
                client, _project(), "GET", "https://example.com/robots.txt", max_response_bytes=10
            )

    with pytest.raises(OutboundSafetyError, match="10-byte"):
        asyncio.run(run())
