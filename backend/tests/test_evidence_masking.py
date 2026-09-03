from app.evidence.masking import is_masking_verifiable, mask_body, mask_cookies, mask_headers


def test_mask_headers_masks_authorization_and_cookie_only():
    headers = {"Authorization": "Bearer sk-verysecrettoken123", "Cookie": "session=abc123def456", "Content-Type": "application/json"}
    masked = mask_headers(headers)

    assert masked["Content-Type"] == "application/json"
    assert masked["Authorization"] != headers["Authorization"]
    assert masked["Authorization"].startswith("Bear")
    assert "verysecret" not in masked["Authorization"]
    assert masked["Cookie"] != headers["Cookie"]


def test_mask_headers_leaves_short_or_empty_values_alone():
    headers = {"X-Custom": "", "Authorization": ""}
    masked = mask_headers(headers)
    assert masked["Authorization"] == ""


def test_mask_cookies_masks_value_but_keeps_name_and_attributes():
    masked = mask_cookies(["sessionid=abcdef123456; Path=/; HttpOnly"])
    assert masked[0].startswith("sessionid=")
    assert "abcdef123456" not in masked[0]
    assert "Path=/; HttpOnly" in masked[0]


def test_mask_body_masks_password_and_token_fields_only():
    body = '{"username": "alice", "password": "hunter2verysecret", "token": "abcdefghijklmnop"}'
    masked = mask_body(body)

    assert '"username": "alice"' in masked
    assert "hunter2verysecret" not in masked
    assert "abcdefghijklmnop" not in masked


def test_mask_body_none_and_empty_pass_through():
    assert mask_body(None) is None
    assert mask_body("") == ""


def test_is_masking_verifiable_true_for_json_and_empty():
    assert is_masking_verifiable(None) is True
    assert is_masking_verifiable("") is True
    assert is_masking_verifiable('{"a": 1}') is True


def test_is_masking_verifiable_false_for_non_json_body():
    assert is_masking_verifiable("plain text with maybe a password=hunter2 in it") is False
