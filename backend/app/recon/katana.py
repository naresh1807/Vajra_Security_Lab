"""Constrained ProjectDiscovery Katana adapter."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.core.config import settings
from app.projects.models import Project
from app.surface.safety import SafeEndpoint, redact_url_for_log, sanitize_endpoint_url
from app.tools.adapter import ToolExecutionError, ToolUnavailableError, detect_version, run_tool

DESTRUCTIVE_CRAWL_REGEX = r"(?i)/(logout|log-out|signout|sign-out|delete|remove|destroy|reset|unsubscribe|terminate|deactivate|close-account|cancel-account)(/|\?|$)"


@dataclass(frozen=True)
class CrawledEndpoint:
    endpoint: SafeEndpoint
    status_code: int | None
    content_type: str | None


@dataclass(frozen=True)
class RejectedCrawl:
    url: str
    reason: str


@dataclass
class KatanaDiscovery:
    endpoints: list[CrawledEndpoint] = field(default_factory=list)
    rejections: list[RejectedCrawl] = field(default_factory=list)
    available: bool = False
    version: str | None = None
    command: str | None = None
    error: str | None = None


def _response_metadata(value: dict) -> tuple[int | None, str | None]:
    response = value.get("response") if isinstance(value.get("response"), dict) else {}
    try:
        status = int(response.get("status_code"))
    except (TypeError, ValueError):
        status = None
    headers = response.get("headers") if isinstance(response.get("headers"), dict) else {}
    content_type = headers.get("content_type") or headers.get("content-type")
    return status, str(content_type)[:255] if content_type else None


def parse_katana_output(output: str, project: Project) -> tuple[list[CrawledEndpoint], list[RejectedCrawl]]:
    accepted: dict[str, CrawledEndpoint] = {}
    rejected: list[RejectedCrawl] = []
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        request = value.get("request") if isinstance(value.get("request"), dict) else {}
        method = str(request.get("method") or "GET").upper()
        raw_url = str(request.get("endpoint") or value.get("endpoint") or value.get("url") or "")
        if not raw_url:
            continue
        if method != "GET":
            rejected.append(RejectedCrawl(redact_url_for_log(raw_url), f"Crawler emitted disallowed method {method}; only GET is retained."))
            continue
        endpoint, reason = sanitize_endpoint_url(project, raw_url)
        if endpoint is None:
            rejected.append(RejectedCrawl(redact_url_for_log(raw_url), reason or "URL rejected by crawl safety policy."))
            continue
        status, content_type = _response_metadata(value)
        accepted[endpoint.normalized_url] = CrawledEndpoint(endpoint, status, content_type)
    return list(accepted.values()), rejected


def _rate_args(rate_limit_rps: float) -> list[str]:
    if rate_limit_rps < 1:
        return ["-rate-limit-minute", str(max(1, int(rate_limit_rps * 60)))]
    return ["-rate-limit", str(max(1, int(rate_limit_rps)))]


async def crawl_with_katana(project: Project, urls: list[str]) -> KatanaDiscovery:
    if not settings.katana_enabled:
        return KatanaDiscovery(error="Katana integration is disabled by configuration.")
    inputs = sorted(set(urls))
    if not inputs:
        return KatanaDiscovery(error="No live, safe URLs were available for Katana.")
    args = [
        "-silent", "-jsonl", "-omit-raw", "-omit-body", "-no-color",
        "-depth", str(max(1, min(settings.katana_depth, 3))),
        "-js-crawl", "-ignore-query-params", "-field-scope", "fqdn",
        "-disable-redirects", "-crawl-out-scope", DESTRUCTIVE_CRAWL_REGEX,
        "-concurrency", "1", "-parallelism", "1",
        "-timeout", str(max(1, int(settings.http_timeout_seconds))),
        "-max-response-size", str(settings.katana_max_response_size),
        *_rate_args(project.rate_limit_rps),
    ]
    try:
        version = await detect_version(settings.katana_executable)
        result = await run_tool(
            settings.katana_executable, args,
            input_text="\n".join(inputs) + "\n",
            timeout_seconds=settings.external_tool_timeout_seconds,
            max_output_bytes=settings.external_tool_max_output_bytes,
        )
        if result.returncode != 0:
            return KatanaDiscovery(
                available=True, version=version, command=result.display_command,
                error=(result.stderr.strip() or f"Katana exited with code {result.returncode}")[:1000],
            )
        endpoints, rejections = parse_katana_output(result.stdout, project)
        return KatanaDiscovery(endpoints, rejections, True, version, result.display_command)
    except (ToolUnavailableError, ToolExecutionError) as exc:
        return KatanaDiscovery(error=str(exc))
