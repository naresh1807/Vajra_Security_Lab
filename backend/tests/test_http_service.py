import asyncio
from types import SimpleNamespace

import pytest

from app.http import service as http_service
from app.core import outbound
from app.http.service import ScopeBlockedError, send_http_request
from app.projects.models import Project


class _FakeSession:
    """Stand-in for a DB session - send_http_request only needs add()/commit()
    to log the ScopeAuditLog entry before the scope decision is checked."""

    def add(self, obj):
        pass

    def commit(self):
        pass


def _project(**overrides) -> Project:
    defaults = dict(
        name="Test Program",
        target="example.com",
        allowed_domains=["example.com"],
        allowed_subdomains=[],
        excluded_assets=[],
        rate_limit_rps=5.0,
    )
    defaults.update(overrides)
    return Project(**defaults)


def test_send_http_request_blocks_out_of_scope_target():
    project = _project()
    db = _FakeSession()

    with pytest.raises(ScopeBlockedError):
        asyncio.run(send_http_request(db, project, "GET", "https://evil.org/", {}, None))


def test_send_http_request_never_stores_a_blank_error(monkeypatch):
    """httpx's own exceptions (ConnectTimeout, ReadTimeout, ...) frequently
    stringify to "" - a real "FAILED, no message" case seen against a
    flaky test target. A failed transaction must always carry *some*
    explanation, even when the underlying exception's message is empty."""

    class _EmptyMessageTimeout(Exception):
        def __str__(self):
            return ""

    class _RaisingClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, *a, **kw):
            raise _EmptyMessageTimeout()

    monkeypatch.setattr(http_service, "httpx", SimpleNamespace(AsyncClient=_RaisingClient))
    monkeypatch.setattr(outbound, "_resolve_addresses", lambda host: {"93.184.216.34"})

    project = _project(target="reachable-but-slow.example.com", allowed_domains=["reachable-but-slow.example.com"])
    db = _FakeSession()

    fields = asyncio.run(
        send_http_request(db, project, "GET", "https://reachable-but-slow.example.com/", {}, None)
    )

    assert fields["status_code"] is None
    assert fields["error"]  # never falsy
    assert "_EmptyMessageTimeout" in fields["error"]
