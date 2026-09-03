from app.recon.priority import score_hostname


def test_api_host_scores_high_with_reason():
    result = score_hostname("api.example.com")
    assert result.score >= 30
    assert result.category == "api"
    assert any("API" in r for r in result.reasons)


def test_rest_host_scores_as_api():
    """rest.vulnweb.com is a real live host found during dev testing that
    scored 0/LOW despite being API-shaped - "rest" belongs in the api signal."""
    result = score_hostname("rest.example.com")
    assert result.category == "api"
    assert result.level == "HIGH"


def test_auth_host_scores_high():
    result = score_hostname("login.example.com")
    assert result.score >= 28
    assert result.level == "MEDIUM" or result.level == "HIGH"


def test_plain_host_has_no_signal_reason():
    result = score_hostname("www.example.com")
    assert result.score == 0
    assert result.level == "LOW"
    assert result.category is None


def test_multiple_signals_stack_and_cap_at_100():
    result = score_hostname("admin-api-auth.example.com")
    assert result.score <= 100
    assert result.score >= 30
