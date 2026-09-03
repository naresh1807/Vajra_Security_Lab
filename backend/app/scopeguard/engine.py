"""
Vajra ScopeGuard (Section 5).

Every target, before any recon or HTTP operation touches it, is normalized
and checked against the owning project's scope configuration. No security
module in this codebase is permitted to skip this check - `recon/service.py`
and `http/` (future) call `check_scope` before making a single outbound
request to a target.

Pipeline:
    target -> normalize -> exclusions -> allowed scope -> rate limit -> decision
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.projects.models import Project
from app.core.config import settings
from app.scopeguard.models import ScopeDecision

_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def normalize_target(raw: str) -> str:
    """Reduce a URL, host:port, or bare hostname down to a bare lowercase host.

    Examples:
        "https://Api.Example.com:8443/v1/users?x=1" -> "api.example.com"
        "example.com."                               -> "example.com"
        "  example.com  "                             -> "example.com"
    """
    value = raw.strip()
    if not value:
        return ""

    if not _SCHEME_RE.match(value):
        value = f"//{value}"
    else:
        # urlsplit needs a scheme to treat the host as netloc; normalize any
        # scheme so we still land in .netloc.
        value = _SCHEME_RE.sub("//", value, count=1)

    parts = urlsplit(value)
    host = parts.hostname or ""
    return host.rstrip(".").lower()


def _matches_domain_or_subdomain(host: str, domain: str) -> bool:
    domain = domain.strip().lower().lstrip(".")
    if not domain:
        return False
    return host == domain or host.endswith(f".{domain}")


def _matches_pattern(host: str, pattern: str) -> bool:
    """Supports exact hosts and simple '*.domain.com' wildcard patterns."""
    pattern = pattern.strip().lower()
    if not pattern:
        return False
    if pattern.startswith("*."):
        return _matches_domain_or_subdomain(host, pattern[2:])
    return host == pattern


@dataclass
class ScopeCheckResult:
    normalized_target: str
    decision: ScopeDecision
    reason: str


def check_scope(project: Project, raw_target: str) -> ScopeCheckResult:
    host = normalize_target(raw_target)

    if not host:
        return ScopeCheckResult(host, ScopeDecision.BLOCKED, "Target could not be parsed into a hostname.")

    # 1. Exclusions always win, even over an otherwise-allowed domain.
    for excluded in project.excluded_assets:
        if _matches_pattern(host, excluded) or _matches_domain_or_subdomain(host, excluded.lstrip("*.")):
            return ScopeCheckResult(
                host, ScopeDecision.BLOCKED, f"'{host}' matches an excluded asset ('{excluded}')."
            )

    # 2. Must fall under at least one allowed domain.
    allowed_domains = project.allowed_domains or ([project.target] if project.target else [])
    in_allowed_domain = any(_matches_domain_or_subdomain(host, d) for d in allowed_domains)

    if not in_allowed_domain:
        return ScopeCheckResult(
            host,
            ScopeDecision.BLOCKED,
            f"'{host}' is not within the program's allowed domains ({', '.join(allowed_domains) or 'none set'}).",
        )

    # 3. If the program enumerates specific allowed subdomain patterns,
    #    the host must match one of them exactly.
    if project.allowed_subdomains:
        if not any(_matches_pattern(host, p) for p in project.allowed_subdomains):
            return ScopeCheckResult(
                host,
                ScopeDecision.MANUAL_REVIEW,
                f"'{host}' is under an allowed domain but does not match any explicitly allowed "
                "subdomain pattern. Confirm program rules before testing.",
            )

    return ScopeCheckResult(host, ScopeDecision.ALLOWED, f"'{host}' is within authorized scope.")


class RateLimiter:
    """Project token bucket: local for inline dev, atomic Redis for RQ."""

    def __init__(self) -> None:
        self._buckets: dict[int, _Bucket] = {}

    def allow(self, project_id: int, rate_limit_rps: float) -> bool:
        if settings.job_queue_backend == "rq":
            return self._allow_redis(project_id, rate_limit_rps)
        bucket = self._buckets.setdefault(project_id, _Bucket(tokens=rate_limit_rps, capacity=rate_limit_rps))
        return bucket.consume(rate_limit_rps)

    def _allow_redis(self, project_id: int, rate_limit_rps: float) -> bool:
        """Atomic shared token bucket for multi-process production workers."""
        import redis

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        capacity = max(1.0, rate_limit_rps)
        script = """
        local now = redis.call('TIME')
        local now_ms = now[1] * 1000 + math.floor(now[2] / 1000)
        local values = redis.call('HMGET', KEYS[1], 'tokens', 'updated')
        local tokens = tonumber(values[1]) or tonumber(ARGV[2])
        local updated = tonumber(values[2]) or now_ms
        tokens = math.min(tonumber(ARGV[2]), tokens + ((now_ms - updated) / 1000) * tonumber(ARGV[1]))
        local allowed = 0
        if tokens >= 1 then tokens = tokens - 1; allowed = 1 end
        redis.call('HSET', KEYS[1], 'tokens', tokens, 'updated', now_ms)
        redis.call('PEXPIRE', KEYS[1], math.max(2000, math.ceil(2000 / tonumber(ARGV[1]))))
        return allowed
        """
        try:
            return bool(client.eval(script, 1, f"vajra:rate:{project_id}", rate_limit_rps, capacity))
        except redis.RedisError as exc:
            raise RuntimeError("Shared rate limiter is unavailable; outbound request stopped.") from exc


@dataclass
class _Bucket:
    tokens: float
    capacity: float
    last_refill: float = field(default_factory=time.monotonic)

    def consume(self, rate_per_second: float) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * rate_per_second)
        self.last_refill = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


rate_limiter = RateLimiter()
