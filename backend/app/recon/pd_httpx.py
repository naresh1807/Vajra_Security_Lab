"""Optional ProjectDiscovery httpx adapter for in-scope live probing."""
from __future__ import annotations

import json
import ipaddress
from dataclasses import dataclass, field

from app.core.config import settings
from app.scopeguard.engine import normalize_target
from app.tools.adapter import ToolExecutionError, ToolUnavailableError, detect_version, run_tool


@dataclass
class HttpxProbe:
    url: str
    status_code: int
    title: str | None
    server: str | None
    technologies: list[str]
    ip: str | None
    content_length: int | None


@dataclass
class HttpxDiscovery:
    probes: dict[str, HttpxProbe] = field(default_factory=dict)
    available: bool = False
    version: str | None = None
    command: str | None = None
    error: str | None = None


def _technologies(value: object) -> list[str]:
    if isinstance(value, list):
        return sorted({str(item) for item in value if item})
    if isinstance(value, str) and value:
        return [value]
    return []


def _ip(value: dict) -> str | None:
    candidates: list[object] = []
    if isinstance(value.get("a"), list):
        candidates.extend(value["a"])
    candidates.extend([value.get("ip"), value.get("host")])
    for candidate in candidates:
        try:
            return str(ipaddress.ip_address(str(candidate)))
        except ValueError:
            continue
    return None


def parse_httpx_output(output: str, allowed_hosts: set[str]) -> dict[str, HttpxProbe]:
    probes: dict[str, HttpxProbe] = {}
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        host = normalize_target(str(value.get("input") or value.get("url") or value.get("host") or ""))
        if host not in allowed_hosts:
            continue
        try:
            status_code = int(value.get("status_code"))
        except (TypeError, ValueError):
            continue
        url = str(value.get("url") or "")
        candidate = HttpxProbe(
            url=url,
            status_code=status_code,
            title=str(value["title"])[:500] if value.get("title") else None,
            server=str(value.get("webserver") or value.get("server"))[:255] if value.get("webserver") or value.get("server") else None,
            technologies=_technologies(value.get("tech")),
            ip=_ip(value),
            content_length=int(value["content_length"]) if isinstance(value.get("content_length"), int) else None,
        )
        existing = probes.get(host)
        # Prefer an HTTPS response when both schemes were emitted.
        if existing is None or (url.startswith("https://") and not existing.url.startswith("https://")):
            probes[host] = candidate
    return probes


def _rate_args(rate_limit_rps: float) -> list[str]:
    if rate_limit_rps < 1:
        return ["-rate-limit-minute", str(max(1, int(rate_limit_rps * 60)))]
    return ["-rate-limit", str(max(1, int(rate_limit_rps)))]


async def probe_with_httpx(hosts: list[str], rate_limit_rps: float) -> HttpxDiscovery:
    if not settings.projectdiscovery_httpx_enabled:
        return HttpxDiscovery(error="ProjectDiscovery httpx integration is disabled by configuration.")
    normalized = sorted({normalize_target(host) for host in hosts if normalize_target(host)})
    if not normalized:
        return HttpxDiscovery(error="No safe in-scope hosts were provided to ProjectDiscovery httpx.")
    args = [
        "-silent", "-json", "-status-code", "-title", "-tech-detect", "-server", "-ip",
        "-content-length", "-no-color", "-no-fallback", "-threads", "1", *_rate_args(rate_limit_rps),
    ]
    try:
        version = await detect_version(settings.projectdiscovery_httpx_executable)
        result = await run_tool(
            settings.projectdiscovery_httpx_executable,
            args,
            input_text="\n".join(normalized) + "\n",
            timeout_seconds=settings.external_tool_timeout_seconds,
            max_output_bytes=settings.external_tool_max_output_bytes,
        )
        if result.returncode != 0:
            return HttpxDiscovery(
                available=True, version=version, command=result.display_command,
                error=(result.stderr.strip() or f"ProjectDiscovery httpx exited with code {result.returncode}")[:1000],
            )
        return HttpxDiscovery(
            probes=parse_httpx_output(result.stdout, set(normalized)), available=True,
            version=version, command=result.display_command,
        )
    except (ToolUnavailableError, ToolExecutionError) as exc:
        return HttpxDiscovery(error=str(exc))
