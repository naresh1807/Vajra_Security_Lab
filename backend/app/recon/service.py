"""
Vajra Recon Engine (Section 7) - MVP implementation.

Pipeline implemented here:
    ROOT DOMAIN -> SUBDOMAIN DISCOVERY -> DNS RESOLUTION -> LIVE HOST PROBING
    -> TECHNOLOGY DETECTION -> OPTIONAL SAFE CRAWL -> PRIORITIZATION

Design choices, honestly stated:
  - Subdomain discovery is passive-only: crt.sh certificate-transparency
    search (retried on the 502/503s it's known to throw when overloaded)
    plus a DNS-only common-subdomain check as a fallback so recon isn't a
    single point of failure on one third-party service. Neither sends a
    packet to the target - the *results* still go through ScopeGuard
    before anything is stored or probed.
  - Live-host probing is the one stage that talks to the target directly.
    It is gated by check_scope() per host and by the project's own
    rate_limit_rps via the shared token-bucket limiter, exactly as
    Section 5 requires ("No security module should bypass ScopeGuard").
  - Technology detection is header/body-heuristic, not a full fingerprint
    database. It is intentionally simple and easy to extend later (see
    Section 41 - "Show Underlying Tool").
  - Optional Go-tool adapters (subfinder/dnsx/httpx/Katana per Section 7)
    use bounded subprocess execution. ScopeGuard remains authoritative before
    target input and again before crawled endpoints are retained.
"""
from __future__ import annotations

import asyncio
import socket
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.outbound import OutboundSafetyError, request_with_safe_redirects, validate_outbound_url
from app.intelligence.tech_detection import detect_technologies
from app.projects.models import Project
from app.recon.models import Asset, AssetSource, AssetType, ReconJob, ReconJobStatus, ReconStage
from app.recon.dnsx import resolve_with_dnsx
from app.recon.priority import HIGH_PRIORITY_THRESHOLD, score_hostname
from app.recon.subfinder import SubfinderDiscovery, discover_with_subfinder
from app.recon.pd_httpx import probe_with_httpx
from app.recon.katana import KatanaDiscovery, crawl_with_katana
from app.recon.wayback import WaybackDiscovery, discover_wayback_urls
from app.surface.metadata import PublicMetadataDiscovery, discover_public_metadata
from app.surface.service import store_katana_discovery, store_public_metadata, store_wayback_discovery


# Per-project recon pipeline switches (Section 42). Only these optional
# sources can be turned off per project; crt.sh and the DNS fallback always
# run. A project can never enable a source the deployment has disabled.
_RECON_SOURCE_SETTING = {
    "subfinder": "subfinder_enabled",
    "wayback": "wayback_enabled",
    "public_metadata": "public_metadata_enabled",
    "katana": "katana_enabled",
}


def recon_source_enabled(project: Project, key: str) -> bool:
    if not getattr(settings, _RECON_SOURCE_SETTING[key], True):
        return False
    return bool((project.recon_sources or {}).get(key, True))


async def _resolved(value):
    return value
from app.scopeguard.engine import check_scope, rate_limiter
from app.scopeguard.models import ScopeAuditLog, ScopeDecision


async def discover_subdomains_crtsh(domain: str) -> tuple[set[str], bool]:
    """Passive subdomain discovery via crt.sh. Never contacts the target.

    crt.sh is a free, community-run certificate-transparency search engine
    and is frequently slow or briefly overloaded (502/503 responses are
    common under load) - it is retried a couple of times with a generous
    timeout before being treated as unavailable for this run.

    Returns (discovered_hostnames, crtsh_succeeded) so the caller can tell
    "this domain has no CT-logged subdomains" apart from "crt.sh was down",
    which look identical if only the resulting set is inspected.
    """
    subdomains: set[str] = set()
    params = {"q": f"%.{domain}", "output": "json"}
    data: list[dict] = []
    succeeded = False

    async with httpx.AsyncClient(
        timeout=settings.crtsh_timeout_seconds, headers={"User-Agent": settings.http_user_agent}
    ) as client:
        for attempt in range(settings.crtsh_retries + 1):
            try:
                resp = await client.get(settings.crtsh_url, params=params)
                resp.raise_for_status()
                data = resp.json()
                succeeded = True
                break
            except Exception:
                if attempt < settings.crtsh_retries:
                    await asyncio.sleep(1.5 * (attempt + 1))

    for entry in data:
        for name in entry.get("name_value", "").split("\n"):
            name = name.strip().lower().lstrip("*.")
            if name and name.endswith(domain) and "*" not in name:
                subdomains.add(name)

    subdomains.add(domain.lower())
    return subdomains, succeeded


async def bruteforce_common_subdomains(domain: str) -> dict[str, str]:
    """DNS-only fallback subdomain check against a small common-name wordlist.

    Purely passive-adjacent: it only sends DNS A-record queries to public
    resolvers and never contacts the target's web server. A candidate is
    only added if it actually resolves, so this never invents hosts that
    don't exist - it just doesn't depend on crt.sh (or any single
    third-party service) being available.

    Returns {hostname: resolved_ip} (not just a set) so the IP already
    looked up here can be reused later instead of resolving it twice.
    """
    semaphore = asyncio.Semaphore(settings.dns_bruteforce_concurrency)

    async def _check(label: str) -> tuple[str, str | None]:
        fqdn = f"{label}.{domain}"
        async with semaphore:
            ip = await asyncio.to_thread(resolve_host, fqdn)
        return fqdn, ip

    results = await asyncio.gather(*(_check(label) for label in settings.common_subdomain_wordlist))
    return {fqdn: ip for fqdn, ip in results if ip}


def resolve_host(hostname: str) -> str | None:
    try:
        return socket.gethostbyname(hostname)
    except Exception:
        return None


async def probe_host(client: httpx.AsyncClient, project: Project, hostname: str) -> dict:
    for scheme in ("https", "http"):
        try:
            resp = await request_with_safe_redirects(client, project, "GET", f"{scheme}://{hostname}/")
        except Exception:
            continue
        body = (resp.text or "")[:20000]
        body_lower = body.lower()
        title = None
        if "<title>" in body_lower:
            start = body_lower.index("<title>") + len("<title>")
            end = body_lower.find("</title>", start)
            if end != -1:
                title = body[start:end].strip()[:200]
        return {
            "is_live": True,
            "status_code": resp.status_code,
            "server_header": resp.headers.get("server"),
            "page_title": title,
            "technologies": detect_technologies(resp.headers, body_lower),
        }
    return {"is_live": False, "status_code": None, "server_header": None, "page_title": None, "technologies": []}


async def run_recon(project_id: int, job_id: int) -> None:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        job = db.get(ReconJob, job_id)
        if project is None or job is None:
            return

        job.status = ReconJobStatus.RUNNING
        job.stage = ReconStage.SUBDOMAIN_DISCOVERY
        db.commit()

        notes: list[str] = []

        crtsh_result, dns_resolved, subfinder_result, wayback_result = await asyncio.gather(
            discover_subdomains_crtsh(project.target),
            bruteforce_common_subdomains(project.target),
            discover_with_subfinder(project.target)
            if recon_source_enabled(project, "subfinder")
            else _resolved(SubfinderDiscovery(error="subfinder is disabled for this project.")),
            discover_wayback_urls(project.target)
            if recon_source_enabled(project, "wayback")
            else _resolved(WaybackDiscovery(error="Wayback URL discovery is disabled for this project.")),
        )
        crtsh_subdomains, crtsh_ok = crtsh_result
        dns_subdomains = set(dns_resolved.keys())
        subfinder_subdomains = subfinder_result.hosts
        subdomains = crtsh_subdomains | dns_subdomains | subfinder_subdomains

        if not crtsh_ok:
            notes.append(
                "Certificate transparency search (crt.sh) did not return data this run - it's a free public "
                "service that is sometimes temporarily overloaded (HTTP 502/503) or slow. Vajra fell back to "
                "checking a list of common subdomain names via DNS. Re-running recon later may find more via "
                "crt.sh once it recovers."
            )
        dns_only = dns_subdomains - crtsh_subdomains
        if dns_only:
            notes.append(f"{len(dns_only)} subdomain(s) found only via the DNS common-name fallback, not crt.sh.")
        if subfinder_result.available:
            version = f" ({subfinder_result.version})" if subfinder_result.version else ""
            notes.append(
                f"subfinder{version} contributed {len(subfinder_subdomains)} normalized hostname(s). "
                f"Underlying command: {subfinder_result.command}"
            )
        elif settings.subfinder_enabled:
            notes.append(
                "Optional subfinder discovery was unavailable; crt.sh and DNS discovery continued normally. "
                f"Reason: {subfinder_result.error}"
            )

        job.stage = ReconStage.DNS_RESOLUTION
        db.commit()

        allowed_hosts: list[str] = []
        for host in subdomains:
            result = check_scope(project, host)
            db.add(
                ScopeAuditLog(
                    project_id=project.id,
                    target_input=host,
                    normalized_target=result.normalized_target,
                    decision=result.decision,
                    reason=result.reason,
                    operation="recon_subdomain_discovery",
                )
            )
            if result.decision == ScopeDecision.ALLOWED:
                allowed_hosts.append(result.normalized_target)
        db.commit()

        # dnsx receives only hosts that have already passed ScopeGuard. It is
        # never given raw or out-of-scope discovery output.
        dnsx_result = await resolve_with_dnsx(allowed_hosts)
        dnsx_records = dnsx_result.records
        if dnsx_result.available:
            version = f" ({dnsx_result.version})" if dnsx_result.version else ""
            notes.append(
                f"dnsx{version} returned structured DNS records for {len(dnsx_records)} in-scope host(s). "
                f"Underlying command: {dnsx_result.command}"
            )
        elif settings.dnsx_enabled:
            notes.append(
                "Optional dnsx validation was unavailable; Vajra used its built-in DNS resolver. "
                f"Reason: {dnsx_result.error}"
            )

        existing = {a.hostname: a for a in db.query(Asset).filter(Asset.project_id == project.id).all()}
        new_count = 0
        for host in allowed_hosts:
            sources: list[str] = []
            if host in crtsh_subdomains:
                sources.append("crtsh")
            if host in subfinder_subdomains:
                sources.append("subfinder")
            if host in dns_subdomains:
                sources.append("dns")
            if host in existing:
                existing[host].discovery_sources = sorted(set(existing[host].discovery_sources or []) | set(sources))
                if host in dnsx_records:
                    existing[host].dns_records = dnsx_records[host]
                    if dnsx_records[host].get("a"):
                        existing[host].resolved_ip = dnsx_records[host]["a"][0]
                continue
            source = AssetSource.CRTSH if host in crtsh_subdomains else AssetSource.DNS
            asset = Asset(
                project_id=project.id, hostname=host, asset_type=AssetType.SUBDOMAIN,
                source=source, discovery_sources=sources, dns_records=dnsx_records.get(host, {}),
            )
            # Reuse the IP from the DNS fallback step where we already have it;
            # otherwise resolve off the event loop - socket.gethostbyname blocks,
            # and blocking the loop here would stall every other request the
            # API is serving (this is what caused the dashboard to hang).
            dnsx_ipv4 = dnsx_records.get(host, {}).get("a", [])
            asset.resolved_ip = (dnsx_ipv4[0] if dnsx_ipv4 else None) or dns_resolved.get(host) or await asyncio.to_thread(resolve_host, host)
            db.add(asset)
            existing[host] = asset
            new_count += 1
        db.commit()

        job.stage = ReconStage.LIVE_HOST_PROBING
        db.commit()

        preflight_semaphore = asyncio.Semaphore(20)

        async def _preflight(host: str) -> tuple[str, bool]:
            async with preflight_semaphore:
                try:
                    await validate_outbound_url(project, f"https://{host}/")
                    return host, True
                except OutboundSafetyError:
                    return host, False

        preflight = await asyncio.gather(*(_preflight(host) for host in existing))
        safe_probe_hosts = [host for host, safe in preflight if safe]
        blocked_probe_count = len(preflight) - len(safe_probe_hosts)
        if blocked_probe_count:
            notes.append(
                f"{blocked_probe_count} host(s) were not probed because outbound safety validation rejected "
                "their current DNS destination."
            )

        pd_httpx_result = await probe_with_httpx(safe_probe_hosts, project.rate_limit_rps)
        pd_httpx_probes = pd_httpx_result.probes
        if pd_httpx_result.available:
            version = f" ({pd_httpx_result.version})" if pd_httpx_result.version else ""
            notes.append(
                f"ProjectDiscovery httpx{version} returned live metadata for {len(pd_httpx_probes)} host(s). "
                f"Redirect following was disabled. Underlying command: {pd_httpx_result.command}"
            )
        elif settings.projectdiscovery_httpx_enabled:
            notes.append(
                "Optional ProjectDiscovery httpx probing was unavailable; Vajra used its internal safe HTTP "
                f"client. Reason: {pd_httpx_result.error}"
            )

        live_count = 0
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_seconds, headers={"User-Agent": settings.http_user_agent}
        ) as client:
            for host, asset in existing.items():
                if host not in safe_probe_hosts:
                    asset.is_live = False
                    continue
                if asset.resolved_ip is None:
                    asset.resolved_ip = await asyncio.to_thread(resolve_host, host)
                if asset.resolved_ip is None:
                    asset.is_live = False
                    continue

                external_probe = pd_httpx_probes.get(host)
                if external_probe is not None:
                    probe = {
                        "is_live": True,
                        "status_code": external_probe.status_code,
                        "server_header": external_probe.server,
                        "page_title": external_probe.title,
                        "technologies": external_probe.technologies,
                    }
                    asset.probe_source = "projectdiscovery-httpx"
                    if external_probe.ip:
                        asset.resolved_ip = external_probe.ip
                else:
                    while not rate_limiter.allow(project.id, project.rate_limit_rps):
                        await asyncio.sleep(1.0 / max(project.rate_limit_rps, 0.1))
                    probe = await probe_host(client, project, host)
                    asset.probe_source = "vajra-httpx"
                asset.is_live = probe["is_live"]
                asset.status_code = probe["status_code"]
                asset.server_header = probe["server_header"]
                asset.page_title = probe["page_title"]
                asset.technologies = probe["technologies"]
                asset.last_checked_at = datetime.now(timezone.utc)
                if probe["is_live"]:
                    live_count += 1
        db.commit()

        crawl_urls: list[str] = []
        for host, asset in existing.items():
            if not asset.is_live:
                continue
            external = pd_httpx_probes.get(host)
            if external and external.url:
                crawl_urls.append(external.url)
            else:
                crawl_urls.extend([f"https://{host}/", f"http://{host}/"])

        if recon_source_enabled(project, "public_metadata"):
            metadata_result = await discover_public_metadata(project, crawl_urls)
        else:
            metadata_result = PublicMetadataDiscovery()
            notes.append("Public metadata / spec discovery is disabled for this project.")
        metadata_new_endpoints, metadata_new_documents, metadata_rejections = store_public_metadata(
            db, project.id, metadata_result
        )
        if settings.public_metadata_enabled and recon_source_enabled(project, "public_metadata"):
            successful_metadata = sum(
                1 for document in metadata_result.documents if document.status_code == 200 and not document.error
            )
            notes.append(
                f"Public metadata checked {len(metadata_result.documents)} bounded robots/sitemap document(s); "
                f"{successful_metadata} returned parseable content, {metadata_new_documents} were new records, "
                f"and {metadata_new_endpoints} new endpoint(s) were indexed without fetching those endpoints."
            )

        wayback_new_endpoints = 0
        wayback_rejections = 0
        if wayback_result.urls:
            wayback_new_endpoints, wayback_rejections = store_wayback_discovery(
                db, project, wayback_result.urls
            )
            notes.append(
                f"Wayback Machine (passive OSINT) returned {len(wayback_result.urls)} historical URL(s); "
                f"{wayback_new_endpoints} new in-scope endpoint(s) were indexed and {wayback_rejections} "
                "out-of-scope/unsafe URL(s) were recorded. None were fetched."
            )
        elif wayback_result.error:
            notes.append(f"Passive Wayback URL discovery did not contribute this run: {wayback_result.error}")

        if recon_source_enabled(project, "katana"):
            katana_result = await crawl_with_katana(project, crawl_urls)
        else:
            katana_result = KatanaDiscovery(error="Katana crawling is disabled for this project.")
        crawled_new = 0
        crawl_rejections = 0
        if katana_result.available and not katana_result.error:
            crawled_new, crawl_rejections = store_katana_discovery(db, project.id, katana_result)
            version = f" ({katana_result.version})" if katana_result.version else ""
            notes.append(
                f"Katana{version} retained {len(katana_result.endpoints)} safe GET endpoint(s), including "
                f"{crawled_new} new inventory record(s); {len(katana_result.rejections)} emitted URL(s) were "
                f"rejected by Vajra policy. Underlying command: {katana_result.command}"
            )
        elif settings.katana_enabled:
            notes.append(f"Optional Katana crawling did not run successfully: {katana_result.error}")

        if existing and live_count == 0:
            notes.append(
                "None of the discovered hosts responded on HTTP/HTTPS. This can mean the target infrastructure "
                "is temporarily unreachable from this network, the hosts don't serve web traffic on ports "
                "80/443, or a firewall is blocking the connection - it does not necessarily mean the domain is "
                "unused."
            )

        job.stage = ReconStage.PRIORITIZATION
        db.commit()

        high_priority = 0
        for asset in existing.values():
            priority = score_hostname(asset.hostname)
            asset.priority_score = priority.score
            asset.priority_reasons = priority.reasons
            asset.priority_category = priority.category
            asset.recommended_action = priority.recommended_action
            if priority.score >= HIGH_PRIORITY_THRESHOLD:
                high_priority += 1
        db.commit()

        job.stage = ReconStage.DONE
        job.status = ReconJobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        job.summary = {
            "subdomains_discovered": len(subdomains),
            "subfinder_discovered": len(subfinder_subdomains),
            "dnsx_resolved": len(dnsx_records),
            "httpx_probed": len(pd_httpx_probes),
            "wayback_urls": len(wayback_result.urls),
            "new_endpoints": crawled_new + metadata_new_endpoints + wayback_new_endpoints,
            "metadata_documents": len(metadata_result.documents),
            "metadata_rejections": metadata_rejections,
            "crawl_rejections": crawl_rejections,
            "in_scope": len(allowed_hosts),
            "blocked_out_of_scope": len(subdomains) - len(allowed_hosts),
            "new_assets": new_count,
            "live_hosts": live_count,
            "high_priority_assets": high_priority,
        }
        job.notes = notes
        db.commit()
    except Exception as exc:  # keep recon failures contained to the job record
        job = db.get(ReconJob, job_id)
        if job is not None:
            job.status = ReconJobStatus.FAILED
            job.error = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
