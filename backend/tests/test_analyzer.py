from app.analyzer.checks import (
    AnalyzerInput,
    Classification,
    analyze_api_response,
    analyze_auth_behavior,
    analyze_cookies,
    analyze_cors,
    analyze_information_exposure,
    analyze_security_headers,
    analyze_transport_security,
    count_by_classification,
    run_all_analyzers,
)


def _input(**overrides) -> AnalyzerInput:
    defaults = dict(
        url="https://api.example.com/v1/users/1",
        status_code=200,
        request_headers={},
        response_headers={},
        response_cookies=[],
        body="",
    )
    defaults.update(overrides)
    return AnalyzerInput(**defaults)


def test_security_headers_flags_each_missing_header_separately():
    findings = analyze_security_headers(_input(response_headers={"server": "nginx"}))
    titles = [f.title for f in findings]
    assert any("Content-Security-Policy" in t for t in titles)
    assert any("Strict-Transport-Security" in t for t in titles)
    assert len(findings) == 5  # all five checked headers missing


def test_security_headers_all_present_is_informational():
    complete = {
        "content-security-policy": "default-src 'self'",
        "strict-transport-security": "max-age=63072000",
        "x-frame-options": "DENY",
        "x-content-type-options": "nosniff",
        "referrer-policy": "no-referrer",
    }
    findings = analyze_security_headers(_input(response_headers=complete))
    assert len(findings) == 1
    assert findings[0].classification == Classification.INFORMATIONAL


def test_cookies_flags_missing_flags_and_escalates_for_session_like_names():
    findings = analyze_cookies(_input(response_cookies=["sessionid=abc123; Path=/"]))
    assert len(findings) == 1
    assert findings[0].classification == Classification.NEEDS_REVIEW
    assert "HttpOnly" in findings[0].title


def test_cookies_non_sensitive_missing_flags_is_only_interesting():
    findings = analyze_cookies(_input(response_cookies=["theme=dark; Path=/"]))
    assert findings[0].classification == Classification.INTERESTING


def test_cookies_fully_flagged_cookie_has_no_finding():
    findings = analyze_cookies(_input(response_cookies=["sessionid=abc123; HttpOnly; Secure; SameSite=Strict"]))
    assert findings[0].classification == Classification.INFORMATIONAL


def test_cors_reflected_origin_with_credentials_is_potential_finding():
    findings = analyze_cors(
        _input(
            request_headers={"Origin": "https://evil.example"},
            response_headers={
                "access-control-allow-origin": "https://evil.example",
                "access-control-allow-credentials": "true",
            },
        )
    )
    assert findings[0].classification == Classification.POTENTIAL_FINDING


def test_cors_reflected_origin_without_credentials_is_needs_review_not_potential_finding():
    findings = analyze_cors(
        _input(
            request_headers={"Origin": "https://evil.example"},
            response_headers={"access-control-allow-origin": "https://evil.example"},
        )
    )
    assert findings[0].classification == Classification.NEEDS_REVIEW


def test_cors_plain_wildcard_without_credentials_is_informational():
    findings = analyze_cors(_input(response_headers={"access-control-allow-origin": "*"}))
    assert findings[0].classification == Classification.INFORMATIONAL


def test_transport_security_flags_plain_http():
    findings = analyze_transport_security(_input(url="http://example.com/login"))
    assert findings[0].classification == Classification.POTENTIAL_FINDING


def test_transport_security_https_is_informational():
    findings = analyze_transport_security(_input(url="https://example.com/login"))
    assert findings[0].classification == Classification.INFORMATIONAL


def test_information_exposure_flags_versioned_server_header():
    findings = analyze_information_exposure(_input(response_headers={"server": "nginx/1.18.0"}))
    assert any("version" in f.title.lower() for f in findings)


def test_information_exposure_flags_sensitive_path_returning_200():
    findings = analyze_information_exposure(_input(url="https://example.com/.git/config", status_code=200))
    assert any(f.classification == Classification.POTENTIAL_FINDING for f in findings)


def test_api_response_flags_debug_field_in_json_body():
    findings = analyze_api_response(
        _input(response_headers={"content-type": "application/json"}, body='{"error": "boom", "stack_trace": "..."}')
    )
    assert any(f.classification == Classification.NEEDS_REVIEW for f in findings)


def test_auth_behavior_401_without_www_authenticate_is_interesting():
    findings = analyze_auth_behavior(_input(status_code=401))
    assert findings[0].classification == Classification.INTERESTING


def test_run_all_analyzers_and_count_by_classification():
    data = _input(
        url="http://example.com/",
        response_headers={"access-control-allow-origin": "*", "access-control-allow-credentials": "true"},
        response_cookies=["sessionid=abc; Path=/"],
    )
    findings = run_all_analyzers(data)
    counts = count_by_classification(findings)
    assert sum(counts.values()) == len(findings)
    assert counts[Classification.POTENTIAL_FINDING] >= 1  # plain HTTP alone guarantees this
