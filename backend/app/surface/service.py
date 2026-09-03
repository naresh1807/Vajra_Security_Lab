from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.projects.models import Project
from app.recon.katana import KatanaDiscovery
from app.surface.metadata import PublicMetadataDiscovery
from app.surface.models import CrawlRejection, DiscoveredEndpoint, PublicMetadataDocument
from app.surface.safety import redact_url_for_log, sanitize_endpoint_url


def store_katana_discovery(db: Session, project_id: int, discovery: KatanaDiscovery) -> tuple[int, int]:
    existing = {
        (item.normalized_url, item.method.upper()): item
        for item in db.query(DiscoveredEndpoint).filter(DiscoveredEndpoint.project_id == project_id).all()
    }
    now = datetime.now(timezone.utc)
    new_count = 0
    for item in discovery.endpoints:
        endpoint = item.endpoint
        key = (endpoint.normalized_url, "GET")
        record = existing.get(key)
        if record is None:
            record = DiscoveredEndpoint(
                project_id=project_id, url=endpoint.url, normalized_url=endpoint.normalized_url,
                hostname=endpoint.hostname, path=endpoint.path, method="GET",
                query_parameters=endpoint.query_parameters, source="katana",
                status_code=item.status_code, content_type=item.content_type,
            )
            db.add(record); existing[key] = record; new_count += 1
        else:
            record.url = endpoint.url
            record.query_parameters = sorted(set(record.query_parameters or []) | set(endpoint.query_parameters))
            record.status_code = item.status_code if item.status_code is not None else record.status_code
            record.content_type = item.content_type or record.content_type
            record.last_seen_at = now

    # Cap per-run rejection persistence to prevent a noisy tool from growing
    # the audit table without bound. The job note reports the full count.
    for rejection in discovery.rejections[:500]:
        db.add(CrawlRejection(project_id=project_id, url=rejection.url, reason=rejection.reason, source="katana"))
    db.commit()
    return new_count, min(len(discovery.rejections), 500)


def store_wayback_discovery(
    db: Session, project: Project, urls: list[str]
) -> tuple[int, int]:
    """Index passive Wayback URLs as GET endpoints after ScopeGuard.

    Historical URLs are never fetched - they become inventory rows (so the
    API Mapper, Auth Flow, and Access Control Workbench see them) and
    Parameter Intelligence input. Out-of-scope or destructive-looking URLs
    are recorded as rejections, capped per run.
    """
    existing = {
        (item.normalized_url, item.method.upper()): item
        for item in db.query(DiscoveredEndpoint).filter(DiscoveredEndpoint.project_id == project.id).all()
    }
    now = datetime.now(timezone.utc)
    new_count = 0
    rejections: list[tuple[str, str]] = []

    for raw_url in urls:
        endpoint, reason = sanitize_endpoint_url(project, raw_url)
        if endpoint is None:
            rejections.append((redact_url_for_log(raw_url), reason or "Rejected by endpoint safety checks."))
            continue
        key = (endpoint.normalized_url, "GET")
        record = existing.get(key)
        if record is None:
            record = DiscoveredEndpoint(
                project_id=project.id, url=endpoint.url, normalized_url=endpoint.normalized_url,
                hostname=endpoint.hostname, path=endpoint.path, method="GET",
                query_parameters=endpoint.query_parameters, source="wayback",
            )
            db.add(record)
            existing[key] = record
            new_count += 1
        else:
            record.query_parameters = sorted(
                set(record.query_parameters or []) | set(endpoint.query_parameters)
            )
            record.last_seen_at = now

    for url, reason in rejections[:500]:
        db.add(CrawlRejection(project_id=project.id, url=url[:2000], reason=reason, source="wayback"))
    db.commit()
    return new_count, min(len(rejections), 500)


def store_public_metadata(
    db: Session,
    project_id: int,
    discovery: PublicMetadataDiscovery,
) -> tuple[int, int, int]:
    existing_endpoints = {
        (item.normalized_url, item.method.upper()): item
        for item in db.query(DiscoveredEndpoint).filter(DiscoveredEndpoint.project_id == project_id).all()
    }
    new_endpoints = 0
    for item in discovery.endpoints:
        endpoint = item.endpoint
        method = item.method.upper()
        key = (endpoint.normalized_url, method)
        record = existing_endpoints.get(key)
        if record is None:
            record = DiscoveredEndpoint(
                project_id=project_id,
                url=endpoint.url,
                normalized_url=endpoint.normalized_url,
                hostname=endpoint.hostname,
                path=endpoint.path,
                method=method,
                query_parameters=endpoint.query_parameters,
                parameter_details=item.parameter_details,
                request_body_content_types=item.request_body_content_types,
                security_requirements=item.security_requirements,
                tags=item.tags,
                operation_id=item.operation_id,
                summary=item.summary,
                deprecated=item.deprecated,
                request_template=item.request_template,
                source=item.source,
            )
            db.add(record)
            existing_endpoints[key] = record
            new_endpoints += 1
        else:
            record.query_parameters = sorted(set(record.query_parameters or []) | set(endpoint.query_parameters))
            if item.source == "openapi":
                record.url = endpoint.url
                record.parameter_details = item.parameter_details
                record.request_body_content_types = item.request_body_content_types
                record.security_requirements = item.security_requirements
                record.tags = item.tags
                record.operation_id = item.operation_id
                record.summary = item.summary
                record.deprecated = item.deprecated
                record.request_template = item.request_template

    existing_documents = {
        item.url: item
        for item in db.query(PublicMetadataDocument).filter(PublicMetadataDocument.project_id == project_id).all()
    }
    new_documents = 0
    now = datetime.now(timezone.utc)
    for item in discovery.documents:
        record = existing_documents.get(item.url)
        if record is None:
            record = PublicMetadataDocument(project_id=project_id, url=item.url, kind=item.kind)
            db.add(record)
            existing_documents[item.url] = record
            new_documents += 1
        record.kind = item.kind
        record.status_code = item.status_code
        record.content_type = item.content_type
        record.content_sha256 = item.content_sha256
        record.entries = item.entries
        record.error = item.error
        record.fetched_at = now

    for rejection in discovery.rejections[:500]:
        db.add(CrawlRejection(
            project_id=project_id,
            url=rejection.url,
            reason=rejection.reason,
            source=rejection.source,
        ))
    db.commit()
    return new_endpoints, new_documents, min(len(discovery.rejections), 500)
