import json

from app.projects.models import Project
from app.recon.katana import _rate_args, parse_katana_output
from app.surface.safety import sanitize_endpoint_url


def _project(**overrides) -> Project:
    values = {
        "name": "Katana Test",
        "target": "example.com",
        "allowed_domains": ["example.com"],
        "allowed_subdomains": [],
        "excluded_assets": [],
        "rate_limit_rps": 1.0,
    }
    values.update(overrides)
    return Project(**values)


def test_endpoint_sanitizer_redacts_secrets_and_normalizes_query_values():
    endpoint, reason = sanitize_endpoint_url(
        _project(),
        "HTTPS://API.EXAMPLE.COM:443/users/42?page=2&token=super-secret#profile",
    )

    assert reason is None
    assert endpoint is not None
    assert endpoint.url == "https://api.example.com/users/42?page=2&token=%5BREDACTED%5D"
    assert endpoint.normalized_url == "https://api.example.com/users/42?page=&token="
    assert endpoint.query_parameters == ["page", "token"]


def test_endpoint_sanitizer_rejects_destructive_and_out_of_scope_urls():
    destructive, destructive_reason = sanitize_endpoint_url(_project(), "https://example.com/account/delete")
    out_of_scope, scope_reason = sanitize_endpoint_url(_project(), "https://evil.example.net/api")

    assert destructive is None
    assert "destructive" in (destructive_reason or "").lower()
    assert out_of_scope is None
    assert "scopeguard" in (scope_reason or "").lower()


def test_katana_parser_retains_only_safe_gets_and_audits_rejections():
    rows = [
        {
            "request": {"method": "GET", "endpoint": "https://api.example.com/users?id=7&token=raw-secret"},
            "response": {"status_code": 200, "headers": {"content-type": "application/json"}},
        },
        {"request": {"method": "POST", "endpoint": "https://api.example.com/users"}},
        {"request": {"method": "GET", "endpoint": "https://example.com/logout?token=raw-secret"}},
        {"request": {"method": "GET", "endpoint": "https://outside.test/private"}},
    ]
    output = "\n".join(json.dumps(row) for row in rows) + "\nnot-json"

    endpoints, rejections = parse_katana_output(output, _project())

    assert len(endpoints) == 1
    assert endpoints[0].endpoint.url == "https://api.example.com/users?id=7&token=%5BREDACTED%5D"
    assert endpoints[0].endpoint.query_parameters == ["id", "token"]
    assert endpoints[0].status_code == 200
    assert endpoints[0].content_type == "application/json"
    assert len(rejections) == 3
    assert any("only GET" in item.reason for item in rejections)
    assert all("raw-secret" not in item.url for item in rejections)


def test_katana_parser_deduplicates_urls_that_only_differ_by_query_values():
    output = "\n".join(
        json.dumps({"request": {"method": "GET", "endpoint": url}})
        for url in ("https://example.com/search?q=one", "https://example.com/search?q=two")
    )

    endpoints, rejections = parse_katana_output(output, _project())

    assert len(endpoints) == 1
    assert endpoints[0].endpoint.normalized_url == "https://example.com/search?q="
    assert rejections == []


def test_katana_rate_limit_never_rounds_below_one_request_unit():
    assert _rate_args(0.25) == ["-rate-limit-minute", "15"]
    assert _rate_args(0.001) == ["-rate-limit-minute", "1"]
    assert _rate_args(2.9) == ["-rate-limit", "2"]
