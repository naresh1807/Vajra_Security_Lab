from app.js_inspector.extraction import (
    extract_api_routes,
    extract_config_references,
    extract_graphql_urls,
    extract_potential_secrets,
    extract_source_maps,
    extract_websocket_urls,
    mask_secret,
)

SAMPLE_JS = """
const API_BASE_URL = "https://api.example.com/v2";
const client = new ApiClient({ baseUrl: API_BASE_URL });

function fetchUser(id) {
  return fetch("/api/users/" + id);
}

fetch("/api/orders/{id}/items");
fetch("/internal/admin/reports");
fetch("/static/logo.png");

const socket = new WebSocket("wss://realtime.example.com/socket");
const gqlEndpoint = "https://api.example.com/graphql";

//# sourceMappingURL=app.min.js.map

const AWS_KEY = "AKIAABCDEFGHIJKLMNOP";
const apiKey = "sk_live_abcdefghijklmnopqrstuvwx";
"""


def test_extract_api_routes_finds_api_and_internal_paths():
    routes = extract_api_routes(SAMPLE_JS)
    assert "/api/users/" in routes or any(r.startswith("/api/users") for r in routes)
    assert "/api/orders/{id}/items" in routes
    assert "/internal/admin/reports" in routes


def test_extract_api_routes_excludes_static_assets():
    routes = extract_api_routes(SAMPLE_JS)
    assert not any(r.endswith(".png") for r in routes)


def test_extract_graphql_urls():
    urls = extract_graphql_urls(SAMPLE_JS)
    assert "https://api.example.com/graphql" in urls


def test_extract_websocket_urls():
    urls = extract_websocket_urls(SAMPLE_JS)
    assert "wss://realtime.example.com/socket" in urls


def test_extract_source_maps():
    maps = extract_source_maps(SAMPLE_JS)
    assert "app.min.js.map" in maps


def test_extract_config_references():
    refs = extract_config_references(SAMPLE_JS)
    assert refs.get("API_BASE_URL") == "https://api.example.com/v2"


def test_extract_potential_secrets_never_returns_raw_value():
    findings = extract_potential_secrets(SAMPLE_JS)
    labels = {f.label for f in findings}
    assert "AWS Access Key ID" in labels
    assert "Generic API Key/Secret Assignment" in labels

    for f in findings:
        assert "AKIAABCDEFGHIJKLMNOP" not in f.masked_value
        assert "AKIAABCDEFGHIJKLMNOP" not in f.context
        assert "sk_live_abcdefghijklmnopqrstuvwx" not in f.context


def test_mask_secret_keeps_only_first_and_last_four_chars():
    masked = mask_secret("AKIAABCDEFGHIJKLMNOP")
    assert masked.startswith("AKIA")
    assert masked.endswith("MNOP")
    assert "ABCDEFGHIJKL" not in masked


def test_mask_secret_short_value_fully_masked():
    assert mask_secret("abc") == "***"
