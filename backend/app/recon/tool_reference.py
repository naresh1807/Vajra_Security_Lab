"""
Vajra "Show Underlying Tool" reference (Section 41).

Section 41: when Vajra runs something equivalent to subdomain discovery,
explain what it did - and *later* let the hunter see the underlying tool,
the exact command, and what that command means. This module is the
"later": a structured, per-stage breakdown of the recon toolchain, with
the project's real target substituted into every command, so the hunter
gradually learns professional tooling instead of memorizing flags first.

Pure - it reads settings and the project target, runs nothing.
"""
from __future__ import annotations

from app.core.config import settings
from app.projects.models import Project


def _external_status(enabled: bool, executable: str) -> str:
    if not enabled:
        return "Disabled by configuration - Vajra uses its built-in path instead."
    return f"Used when '{executable}' is on PATH (or VAJRA_*_EXECUTABLE points at it); otherwise Vajra falls back to its built-in path."


def build_tool_reference(project: Project) -> dict:
    target = project.target or "example.com"
    rps = project.rate_limit_rps

    stages = [
        {
            "key": "subdomain_discovery",
            "title": "Subdomain discovery",
            "active": False,
            "what_vajra_does": (
                f"Builds a candidate list of hostnames under {target} without sending {target} a single "
                "packet. Every candidate then goes through ScopeGuard before it is stored or probed."
            ),
            "tools": [
                {
                    "name": "crt.sh certificate transparency",
                    "kind": "built-in",
                    "role": "Primary passive source - every certificate ever publicly logged for a name under the domain.",
                    "status": "Always used.",
                    "command": f"curl -s 'https://crt.sh/?q=%25.{target}&output=json'",
                    "command_parts": [
                        {"token": "crt.sh/?q=%25.<domain>", "meaning": "%25 is a URL-encoded '%', so this is the SQL wildcard '%.<domain>' - every subdomain."},
                        {"token": "output=json", "meaning": "Return machine-readable rows instead of the HTML table."},
                    ],
                    "notes": "crt.sh is a free community service and is often slow or briefly overloaded; Vajra retries it and falls back to DNS if it is down.",
                },
                {
                    "name": "DNS common-name fallback",
                    "kind": "built-in",
                    "role": "Resolves a short wordlist of conventional names so recon does not depend on one third-party service.",
                    "status": "Always used, alongside crt.sh.",
                    "command": f"for name in www api admin app staging dev vpn mail; do host \"$name.{target}\"; done",
                    "command_parts": [
                        {"token": "host <name>.<domain>", "meaning": "A DNS A-record lookup against public resolvers - no HTTP request to the target."},
                    ],
                    "notes": "A candidate is kept only if it actually resolves, so this never invents hosts.",
                },
                {
                    "name": "subfinder (ProjectDiscovery)",
                    "kind": "optional external",
                    "role": "Aggregates many passive sources (CT logs, DNS datasets, search engines) into one hostname list.",
                    "status": _external_status(settings.subfinder_enabled, settings.subfinder_executable),
                    "command": f"subfinder -d {target} -silent -json",
                    "command_parts": [
                        {"token": "-d " + target, "meaning": "The root domain to enumerate."},
                        {"token": "-silent", "meaning": "Print only results - no banner or progress noise."},
                        {"token": "-json", "meaning": "One JSON object per line, so Vajra can read the host and which source found it."},
                    ],
                    "notes": "Every hostname it returns is normalized and passed through ScopeGuard before use.",
                },
            ],
        },
        {
            "key": "dns_resolution",
            "title": "DNS resolution",
            "active": False,
            "what_vajra_does": "Resolves the in-scope hostnames to IPs and records, reusing lookups from the discovery step where possible.",
            "tools": [
                {
                    "name": "Built-in resolver",
                    "kind": "built-in",
                    "role": "Standard system DNS resolution, run off the event loop so it never stalls the API.",
                    "status": "Always available as the fallback.",
                    "command": f"host api.{target}",
                    "command_parts": [{"token": "host <fqdn>", "meaning": "Resolve A / AAAA records for one hostname."}],
                    "notes": "",
                },
                {
                    "name": "dnsx (ProjectDiscovery)",
                    "kind": "optional external",
                    "role": "Fast, structured A / AAAA / CNAME resolution for many hosts at once.",
                    "status": _external_status(settings.dnsx_enabled, settings.dnsx_executable),
                    "command": "dnsx -a -aaaa -cname -json -silent   # in-scope hosts on stdin",
                    "command_parts": [
                        {"token": "-a -aaaa -cname", "meaning": "Which record types to return."},
                        {"token": "-json -silent", "meaning": "Structured output, results only."},
                        {"token": "stdin", "meaning": "Vajra pipes in only hostnames that already passed ScopeGuard - never raw discovery output."},
                    ],
                    "notes": "",
                },
            ],
        },
        {
            "key": "live_host_probing",
            "title": "Live-host probing",
            "active": True,
            "what_vajra_does": (
                f"The one recon stage that contacts {target} directly. Every request is gated by ScopeGuard "
                f"per host and by this project's rate limit ({rps} req/s), and only HTTP(S) is allowed."
            ),
            "tools": [
                {
                    "name": "Vajra internal safe client",
                    "kind": "built-in",
                    "role": "Redirect- and SSRF-guarded HTTP client: validates every URL and redirect against scope, blocks private-network destinations, strips credential headers cross-origin.",
                    "status": "Always used - and used to fill in any host an external prober missed.",
                    "command": f"curl -sS -I https://api.{target}/   # then GET for title/tech, rate-limited",
                    "command_parts": [
                        {"token": "-I", "meaning": "Start with a HEAD-style look at status and headers."},
                        {"token": "https then http", "meaning": "Vajra tries HTTPS first, then falls back to HTTP."},
                    ],
                    "notes": "",
                },
                {
                    "name": "httpx (ProjectDiscovery)",
                    "kind": "optional external",
                    "role": "Fast liveness + metadata (status, title, server, tech) for many hosts.",
                    "status": _external_status(settings.projectdiscovery_httpx_enabled, settings.projectdiscovery_httpx_executable),
                    "command": f"httpx -silent -json -no-color -follow-redirects=false -rate-limit {int(max(1, rps))}   # preflighted hosts on stdin",
                    "command_parts": [
                        {"token": "-follow-redirects=false", "meaning": "Vajra disables redirect following so a redirect can't walk the probe off-scope."},
                        {"token": f"-rate-limit {int(max(1, rps))}", "meaning": "Inherits this project's configured request rate."},
                        {"token": "stdin", "meaning": "Only hosts that passed an extra public-address preflight are sent."},
                    ],
                    "notes": "",
                },
            ],
        },
        {
            "key": "technology_detection",
            "title": "Technology detection",
            "active": False,
            "what_vajra_does": "Fingerprints each live host from response headers and body markers as part of the probe - not a separate request.",
            "tools": [
                {
                    "name": "Built-in heuristic fingerprinter",
                    "kind": "built-in",
                    "role": "Header/body pattern matching (Server, X-Powered-By, framework cookies, common markup). Intentionally simple, not a full fingerprint database.",
                    "status": "Always used.",
                    "command": "# no extra request - runs on the probe response Vajra already has",
                    "command_parts": [],
                    "notes": "The real-world heavyweight equivalent is Wappalyzer; Vajra does not run it.",
                },
            ],
        },
        {
            "key": "metadata_discovery",
            "title": "Public metadata & spec discovery",
            "active": True,
            "what_vajra_does": (
                "Fetches only a small, bounded set of conventional documents per live host - robots.txt, capped "
                "sitemap files, and a few standard OpenAPI/Swagger locations. URLs and operations listed inside "
                "them are indexed after ScopeGuard approval but never automatically requested."
            ),
            "tools": [
                {
                    "name": "Vajra metadata fetcher",
                    "kind": "built-in",
                    "role": "Bounded GETs (size- and count-capped) for robots/sitemap/OpenAPI; YAML aliases rejected, external $refs not followed.",
                    "status": f"On by default ({'enabled' if settings.public_metadata_enabled else 'disabled'} now).",
                    "command": f"curl -s https://{target}/robots.txt ; curl -s https://{target}/sitemap.xml ; curl -s https://{target}/openapi.json",
                    "command_parts": [
                        {"token": "robots.txt / sitemap.xml", "meaning": "Advertised paths - manual-review hints, not access controls."},
                        {"token": "openapi.json", "meaning": "If present, its operations are inventoried; none are executed."},
                    ],
                    "notes": "",
                },
            ],
        },
        {
            "key": "crawling",
            "title": "Crawling",
            "active": True,
            "what_vajra_does": (
                "Opt-in and off by default. When enabled, only already-live, already-approved URLs are handed to "
                "the crawler; only parsed GET endpoints that independently pass ScopeGuard are kept."
            ),
            "tools": [
                {
                    "name": "Katana (ProjectDiscovery)",
                    "kind": "optional external",
                    "role": "Same-host, shallow-depth link crawler. No headless browser, no form filling.",
                    "status": _external_status(settings.katana_enabled, settings.katana_executable) if settings.katana_enabled else "Disabled by default - set VAJRA_KATANA_ENABLED=true to opt in.",
                    "command": f"katana -u https://{target}/ -d {settings.katana_depth} -c 1 -rl {int(max(1, rps))} -silent -jc -no-sandbox=false",
                    "command_parts": [
                        {"token": f"-d {settings.katana_depth}", "meaning": "Maximum crawl depth - deliberately shallow."},
                        {"token": "-c 1", "meaning": "One request at a time."},
                        {"token": f"-rl {int(max(1, rps))}", "meaning": "Requests per second - this project's rate limit."},
                        {"token": "-jc", "meaning": "Parse endpoints out of JavaScript files it finds."},
                    ],
                    "notes": "Destructive or session-changing path patterns are excluded, and rejected discoveries are recorded for review.",
                },
            ],
        },
    ]

    return {
        "target": target,
        "rate_limit_rps": rps,
        "note": (
            "Vajra orchestrates these tools so you don't have to juggle a dozen terminals. Every tool here is "
            "either passive or, where it contacts the target, gated by ScopeGuard and this project's rate "
            "limit - and nothing is ever run through a command shell."
        ),
        "stages": stages,
    }
