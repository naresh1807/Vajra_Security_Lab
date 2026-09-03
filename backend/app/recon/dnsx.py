"""Optional ProjectDiscovery dnsx adapter for in-scope DNS evidence."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.core.config import settings
from app.scopeguard.engine import normalize_target
from app.tools.adapter import ToolExecutionError, ToolUnavailableError, detect_version, run_tool


@dataclass
class DnsxDiscovery:
    records: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    available: bool = False
    version: str | None = None
    command: str | None = None
    error: str | None = None


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return sorted({str(item).rstrip(".") for item in value if isinstance(item, str) and item})
    return []


def parse_dnsx_output(output: str, allowed_hosts: set[str]) -> dict[str, dict[str, list[str]]]:
    parsed: dict[str, dict[str, list[str]]] = {}
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        host = normalize_target(str(value.get("host") or value.get("input") or ""))
        if host not in allowed_hosts:
            continue
        records = {
            "a": _string_list(value.get("a")),
            "aaaa": _string_list(value.get("aaaa")),
            "cname": _string_list(value.get("cname")),
        }
        if any(records.values()):
            parsed[host] = records
    return parsed


async def resolve_with_dnsx(hosts: list[str]) -> DnsxDiscovery:
    if not settings.dnsx_enabled:
        return DnsxDiscovery(error="dnsx integration is disabled by configuration.")
    normalized = sorted({normalize_target(host) for host in hosts if normalize_target(host)})
    if not normalized:
        return DnsxDiscovery(error="No in-scope hosts were provided to dnsx.")
    try:
        version = await detect_version(settings.dnsx_executable)
        result = await run_tool(
            settings.dnsx_executable,
            ["-silent", "-json", "-a", "-aaaa", "-cname"],
            input_text="\n".join(normalized) + "\n",
            timeout_seconds=settings.external_tool_timeout_seconds,
            max_output_bytes=settings.external_tool_max_output_bytes,
        )
        if result.returncode != 0:
            return DnsxDiscovery(
                available=True, version=version, command=result.display_command,
                error=(result.stderr.strip() or f"dnsx exited with code {result.returncode}")[:1000],
            )
        return DnsxDiscovery(
            records=parse_dnsx_output(result.stdout, set(normalized)), available=True,
            version=version, command=result.display_command,
        )
    except (ToolUnavailableError, ToolExecutionError) as exc:
        return DnsxDiscovery(error=str(exc))
