import asyncio
from types import SimpleNamespace

from app.recon import service


class _AlwaysFailClient:
    """Fake httpx.AsyncClient that simulates crt.sh being down (e.g. 502s)."""

    def __init__(self, *args, **kwargs):
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        self.calls += 1
        raise RuntimeError("simulated crt.sh failure")


def test_discover_subdomains_crtsh_reports_failure_after_retries(monkeypatch):
    """When crt.sh is unavailable, the caller must be told (crtsh_ok=False),
    not silently handed back a result indistinguishable from 'no subdomains
    exist' - see the vulnweb.com 502 incident this test guards against."""
    monkeypatch.setattr(service, "httpx", SimpleNamespace(AsyncClient=_AlwaysFailClient))
    monkeypatch.setattr(service.settings, "crtsh_retries", 1)

    hosts, ok = asyncio.run(service.discover_subdomains_crtsh("example.com"))

    assert ok is False
    assert hosts == {"example.com"}


def test_bruteforce_common_subdomains_only_returns_resolvable_hosts(monkeypatch):
    monkeypatch.setattr(service.settings, "common_subdomain_wordlist", ["api", "doesnotexist"])
    monkeypatch.setattr(service.settings, "dns_bruteforce_concurrency", 5)

    def fake_resolve(hostname: str):
        return "1.2.3.4" if hostname == "api.example.com" else None

    monkeypatch.setattr(service, "resolve_host", fake_resolve)

    result = asyncio.run(service.bruteforce_common_subdomains("example.com"))

    assert result == {"api.example.com": "1.2.3.4"}
