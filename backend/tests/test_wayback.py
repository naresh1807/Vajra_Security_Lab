"""
Passive Wayback Machine URL discovery (Section 7).

The CDX parser (in-scope filtering, de-dup, cap), the fetch's guard
rails (disabled / bad domain / oversized response), and the store step
that turns historical URLs into ScopeGuard-approved GET endpoints
without ever fetching them.
"""
import asyncio
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.projects.models import Project
from app.recon import wayback
from app.recon.wayback import discover_wayback_urls, parse_cdx_output
from app.surface.models import CrawlRejection, DiscoveredEndpoint
from app.surface.service import store_wayback_discovery


# --- parse_cdx_output --------------------------------------------------

def test_parser_keeps_in_scope_http_urls_and_dedupes():
    text = "\n".join([
        "https://api.example.com/v1/users?id=1",
        "http://example.com/search?q=x",
        "https://api.example.com/v1/users?id=1",  # duplicate
        "https://evil.com/phish",                  # off-domain
        "ftp://example.com/f",                      # non-http
        "not a url",
    ])
    assert parse_cdx_output(text, "example.com", 100) == [
        "https://api.example.com/v1/users?id=1",
        "http://example.com/search?q=x",
    ]


def test_parser_respects_the_limit():
    text = "\n".join(f"https://example.com/{i}" for i in range(50))
    assert len(parse_cdx_output(text, "example.com", 10)) == 10


# --- discover_wayback_urls guard rails --------------------------------

def test_disabled_by_config(monkeypatch):
    monkeypatch.setattr(wayback.settings, "wayback_enabled", False)
    result = asyncio.run(discover_wayback_urls("example.com"))
    assert result.urls == []
    assert "disabled by configuration" in result.error


def test_rejects_a_non_domain_target(monkeypatch):
    monkeypatch.setattr(wayback.settings, "wayback_enabled", True)
    result = asyncio.run(discover_wayback_urls("not a domain"))
    assert result.urls == []
    assert "valid DNS domain" in result.error


def test_oversized_response_is_refused(monkeypatch):
    class _BigClient:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, *a, **k):
            return SimpleNamespace(content=b"x" * 50, raise_for_status=lambda: None)

    monkeypatch.setattr(wayback.settings, "wayback_enabled", True)
    monkeypatch.setattr(wayback.settings, "wayback_max_response_bytes", 10)
    monkeypatch.setattr(wayback, "httpx", SimpleNamespace(AsyncClient=_BigClient))
    result = asyncio.run(discover_wayback_urls("example.com"))
    assert result.urls == []
    assert "safety limit" in result.error


# --- store_wayback_discovery -----------------------------------------

def _project(db: Session) -> Project:
    project = Project(
        name="WB", target="example.com", allowed_domains=["example.com"],
        allowed_subdomains=[], excluded_assets=["secret.example.com"], rate_limit_rps=1.0,
    )
    db.add(project)
    db.flush()
    return project


def test_store_indexes_in_scope_urls_as_get_endpoints_with_params():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project(db)
        new_count, rejected = store_wayback_discovery(db, project, [
            "https://api.example.com/v1/orders?status=open&page=2",
            "https://api.example.com/v1/orders?status=open&page=2",  # dedupes to the same shape
            "https://secret.example.com/admin",                       # excluded asset -> rejected
            "https://other.com/x",                                    # out of scope -> rejected
            "https://api.example.com/account/delete",                 # destructive segment -> rejected
        ])
        db.commit()

        endpoints = db.query(DiscoveredEndpoint).filter_by(project_id=project.id).all()
        rejections = db.query(CrawlRejection).filter_by(project_id=project.id).all()

    assert new_count == 1
    assert rejected == 3
    assert endpoints[0].source == "wayback"
    assert endpoints[0].method == "GET"
    assert endpoints[0].path == "/v1/orders"
    assert set(endpoints[0].query_parameters) == {"status", "page"}
    assert len(rejections) == 3
    assert all(r.source == "wayback" for r in rejections)


def test_store_is_idempotent_for_the_same_url_shape():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project(db)
        urls = ["https://api.example.com/v1/orders?status=open"]

        first, _ = store_wayback_discovery(db, project, urls)
        db.commit()
        second, _ = store_wayback_discovery(db, project, urls)
        db.commit()
        rows = db.query(DiscoveredEndpoint).filter_by(project_id=project.id).all()

    assert first == 1
    assert second == 0  # re-seen, not re-created
    assert len(rows) == 1
    assert rows[0].query_parameters == ["status"]
