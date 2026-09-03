from app.projects.models import Project
from app.core.config import settings
from app.scopeguard.engine import RateLimiter, normalize_target, check_scope
from app.scopeguard.models import ScopeDecision


def _project(**overrides) -> Project:
    defaults = dict(
        name="Test Program",
        target="example.com",
        allowed_domains=["example.com"],
        allowed_subdomains=[],
        excluded_assets=[],
        rate_limit_rps=1.0,
    )
    defaults.update(overrides)
    return Project(**defaults)


def test_normalize_strips_scheme_port_path_case():
    assert normalize_target("https://API.Example.com:8443/v1/users?x=1") == "api.example.com"


def test_normalize_strips_trailing_dot_and_whitespace():
    assert normalize_target("  example.com.  ") == "example.com"


def test_allowed_root_domain():
    project = _project()
    result = check_scope(project, "example.com")
    assert result.decision == ScopeDecision.ALLOWED


def test_allowed_subdomain_of_root_domain():
    project = _project()
    result = check_scope(project, "api.example.com")
    assert result.decision == ScopeDecision.ALLOWED


def test_blocked_out_of_scope_domain():
    project = _project()
    result = check_scope(project, "not-example.org")
    assert result.decision == ScopeDecision.BLOCKED


def test_excluded_asset_blocks_even_if_in_domain():
    project = _project(excluded_assets=["staging.example.com"])
    result = check_scope(project, "staging.example.com")
    assert result.decision == ScopeDecision.BLOCKED
    assert "excluded" in result.reason.lower()


def test_allowed_subdomains_whitelist_forces_manual_review():
    project = _project(allowed_subdomains=["api.example.com"])
    result = check_scope(project, "other.example.com")
    assert result.decision == ScopeDecision.MANUAL_REVIEW


def test_allowed_subdomains_whitelist_permits_match():
    project = _project(allowed_subdomains=["api.example.com"])
    result = check_scope(project, "api.example.com")
    assert result.decision == ScopeDecision.ALLOWED


def test_wildcard_pattern_in_excluded_assets():
    project = _project(excluded_assets=["*.internal.example.com"])
    result = check_scope(project, "db.internal.example.com")
    assert result.decision == ScopeDecision.BLOCKED


def test_rq_mode_uses_shared_rate_limiter(monkeypatch):
    limiter = RateLimiter()
    called = []
    monkeypatch.setattr(settings, "job_queue_backend", "rq")
    monkeypatch.setattr(limiter, "_allow_redis", lambda project_id, rate: called.append((project_id, rate)) or True)
    assert limiter.allow(7, 2.5) is True
    assert called == [(7, 2.5)]
