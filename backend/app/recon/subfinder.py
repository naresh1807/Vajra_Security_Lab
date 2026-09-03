"""Optional ProjectDiscovery subfinder adapter."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.core.config import settings
from app.scopeguard.engine import normalize_target
from app.tools.adapter import ToolExecutionError, ToolUnavailableError, detect_version, run_tool

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)


@dataclass
class SubfinderDiscovery:
    hosts: set[str] = field(default_factory=set)
    available: bool = False
    version: str | None = None
    command: str | None = None
    error: str | None = None


def parse_subfinder_output(output: str, domain: str) -> set[str]:
    hosts: set[str] = set()
    root = domain.lower().rstrip(".")
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        candidate = line
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                candidate = str(value.get("host") or value.get("name") or "")
        except json.JSONDecodeError:
            pass  # Older subfinder versions can emit plain hostnames.
        host = normalize_target(candidate)
        if host and (host == root or host.endswith(f".{root}")):
            hosts.add(host)
    return hosts


async def discover_with_subfinder(domain: str) -> SubfinderDiscovery:
    if not settings.subfinder_enabled:
        return SubfinderDiscovery(error="subfinder integration is disabled by configuration.")
    root = normalize_target(domain)
    if not DOMAIN_RE.fullmatch(root):
        return SubfinderDiscovery(error="Project target is not a valid DNS domain for subfinder.")
    try:
        version = await detect_version(settings.subfinder_executable)
        result = await run_tool(
            settings.subfinder_executable,
            ["-d", root, "-silent", "-json"],
            timeout_seconds=settings.external_tool_timeout_seconds,
            max_output_bytes=settings.external_tool_max_output_bytes,
        )
        if result.returncode != 0:
            return SubfinderDiscovery(
                available=True, version=version, command=result.display_command,
                error=(result.stderr.strip() or f"subfinder exited with code {result.returncode}")[:1000],
            )
        return SubfinderDiscovery(
            hosts=parse_subfinder_output(result.stdout, root), available=True,
            version=version, command=result.display_command,
        )
    except (ToolUnavailableError, ToolExecutionError) as exc:
        return SubfinderDiscovery(error=str(exc))
