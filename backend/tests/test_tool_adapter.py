import asyncio
import sys

import pytest

from app.recon.subfinder import parse_subfinder_output
from app.recon.dnsx import parse_dnsx_output
from app.recon.pd_httpx import _rate_args, parse_httpx_output
from app.tools.adapter import ToolExecutionError, run_tool


def test_subfinder_parser_accepts_jsonl_and_plain_output_but_rejects_other_domains():
    output = "\n".join([
        '{"host":"api.example.com","source":"crtsh"}',
        "admin.example.com",
        '{"host":"evil.org"}',
        '{"host":"not-example.com"}',
        "garbage output",
    ])
    assert parse_subfinder_output(output, "example.com") == {"api.example.com", "admin.example.com"}


def test_dnsx_parser_keeps_only_requested_hosts_and_structured_records():
    output = "\n".join([
        '{"host":"api.example.com","a":["203.0.113.10"],"aaaa":["2001:db8::10"],"cname":["edge.example.net."]}',
        '{"host":"evil.org","a":["127.0.0.1"]}',
        "not-json",
    ])
    assert parse_dnsx_output(output, {"api.example.com"}) == {
        "api.example.com": {
            "a": ["203.0.113.10"],
            "aaaa": ["2001:db8::10"],
            "cname": ["edge.example.net"],
        }
    }


def test_projectdiscovery_httpx_parser_rejects_unrequested_hosts_and_prefers_https():
    output = "\n".join([
        '{"input":"api.example.com","url":"http://api.example.com","status_code":301,"title":"redirect"}',
        '{"input":"api.example.com","url":"https://api.example.com","status_code":200,"title":"API","tech":["nginx"],"a":["203.0.113.20"]}',
        '{"input":"evil.org","url":"https://evil.org","status_code":200}',
        '{"input":"api.example.com","url":"https://api.example.com","status_code":"invalid"}',
    ])
    probes = parse_httpx_output(output, {"api.example.com"})
    assert set(probes) == {"api.example.com"}
    assert probes["api.example.com"].url == "https://api.example.com"
    assert probes["api.example.com"].status_code == 200
    assert probes["api.example.com"].technologies == ["nginx"]
    assert probes["api.example.com"].ip == "203.0.113.20"


def test_projectdiscovery_httpx_rate_limit_never_exceeds_project_setting():
    assert _rate_args(5.8) == ["-rate-limit", "5"]
    assert _rate_args(0.5) == ["-rate-limit-minute", "30"]
    assert _rate_args(0.01) == ["-rate-limit-minute", "1"]


def test_tool_arguments_are_not_interpreted_by_a_shell():
    marker = "; echo SHOULD_NOT_EXECUTE"
    result = asyncio.run(run_tool(
        sys.executable,
        ["-c", "import sys; print(sys.argv[1])", marker],
        timeout_seconds=5,
        max_output_bytes=4096,
    ))
    assert result.returncode == 0
    assert result.stdout.strip() == marker


def test_tool_stdin_is_passed_without_a_shell():
    payload = "api.example.com\n; echo SHOULD_NOT_EXECUTE\n"
    result = asyncio.run(run_tool(
        sys.executable,
        ["-c", "import sys; print(sys.stdin.read(), end='')"],
        input_text=payload,
        timeout_seconds=5,
        max_output_bytes=4096,
    ))
    assert result.stdout.replace("\r\n", "\n") == payload


def test_tool_timeout_kills_process():
    with pytest.raises(ToolExecutionError, match="timed out"):
        asyncio.run(run_tool(
            sys.executable,
            ["-c", "import time; time.sleep(2)"],
            timeout_seconds=0.05,
            max_output_bytes=4096,
        ))


def test_tool_output_limit_is_enforced():
    with pytest.raises(ToolExecutionError, match="output exceeded"):
        asyncio.run(run_tool(
            sys.executable,
            ["-c", "print('x' * 10000)"],
            timeout_seconds=5,
            max_output_bytes=100,
        ))
