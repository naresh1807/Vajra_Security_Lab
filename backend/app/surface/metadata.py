"""Bounded discovery of public robots.txt and sitemap metadata."""
from __future__ import annotations

import asyncio
import hashlib
import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree

import httpx
import yaml
from yaml.events import AliasEvent

from app.core.config import settings
from app.core.outbound import OutboundSafetyError, request_with_safe_redirects
from app.projects.models import Project
from app.scopeguard.engine import rate_limiter
from app.surface.safety import SafeEndpoint, redact_url_for_log, sanitize_endpoint_url


@dataclass(frozen=True)
class MetadataEndpoint:
    endpoint: SafeEndpoint
    source: str
    method: str = "GET"
    parameter_details: list[dict] = field(default_factory=list)
    request_body_content_types: list[str] = field(default_factory=list)
    security_requirements: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    operation_id: str | None = None
    summary: str | None = None
    deprecated: bool = False
    request_template: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MetadataRejection:
    url: str
    reason: str
    source: str


@dataclass
class MetadataDocument:
    url: str
    kind: str
    status_code: int | None = None
    content_type: str | None = None
    content_sha256: str | None = None
    entries: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None


@dataclass
class PublicMetadataDiscovery:
    documents: list[MetadataDocument] = field(default_factory=list)
    endpoints: list[MetadataEndpoint] = field(default_factory=list)
    rejections: list[MetadataRejection] = field(default_factory=list)


_HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
_OPENAPI_PATHS = (
    "/openapi.json", "/swagger.json", "/openapi.yaml", "/swagger.yaml", "/v3/api-docs",
)


class _NoAliasSafeLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects aliases to prevent expansion bombs."""

    def compose_node(self, parent, index):
        if self.check_event(AliasEvent):
            raise yaml.YAMLError("YAML aliases are not accepted in API specifications.")
        return super().compose_node(parent, index)


def _candidate(
    project: Project,
    source_url: str,
    value: str,
    entry_kind: str,
    source: str,
) -> tuple[dict[str, str] | None, MetadataEndpoint | None, MetadataRejection | None]:
    raw_url = urljoin(source_url, value.strip())
    endpoint, reason = sanitize_endpoint_url(project, raw_url)
    if endpoint is None:
        return None, None, MetadataRejection(redact_url_for_log(raw_url), reason or "Metadata URL rejected.", source)
    entry = {"type": entry_kind, "value": endpoint.url}
    # robots.txt permits wildcard path patterns. Retain the safely redacted
    # evidence, but do not represent a pattern as a concrete endpoint.
    concrete = "*" not in value and "$" not in value
    return entry, MetadataEndpoint(endpoint, source) if concrete else None, None


def parse_robots(
    project: Project,
    document_url: str,
    text: str,
) -> tuple[list[dict[str, str]], list[MetadataEndpoint], list[str], list[MetadataRejection]]:
    entries: list[dict[str, str]] = []
    endpoints: list[MetadataEndpoint] = []
    sitemap_urls: list[str] = []
    rejections: list[MetadataRejection] = []
    limit = settings.public_metadata_max_entries_per_document

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        directive, value = (part.strip() for part in line.split(":", 1))
        kind = directive.lower()
        if kind not in {"allow", "disallow", "sitemap"} or not value:
            continue
        entry, endpoint, rejection = _candidate(project, document_url, value, kind, "robots")
        if rejection:
            rejections.append(rejection)
            continue
        if entry and len(entries) < limit:
            entries.append(entry)
        if endpoint:
            endpoints.append(endpoint)
        if kind == "sitemap":
            sitemap_urls.append(urljoin(document_url, value))
    return entries, endpoints, sitemap_urls, rejections


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def parse_sitemap(
    project: Project,
    document_url: str,
    body: str,
) -> tuple[list[dict[str, str]], list[MetadataEndpoint], list[str], list[MetadataRejection]]:
    values: list[tuple[str, str]] = []
    stripped = body.lstrip()
    if stripped.startswith("<"):
        if "<!DOCTYPE" in body.upper() or "<!ENTITY" in body.upper():
            raise ValueError("Sitemap XML declarations and entities are not accepted.")
        try:
            root = ElementTree.fromstring(body)
        except ElementTree.ParseError as exc:
            raise ValueError("Sitemap XML could not be parsed.") from exc
        root_kind = _local_name(root.tag)
        entry_kind = "sitemap" if root_kind == "sitemapindex" else "url"
        values = [
            (entry_kind, element.text.strip())
            for element in root.iter()
            if _local_name(element.tag) == "loc" and element.text and element.text.strip()
        ]
    else:
        values = [("url", line.strip()) for line in body.splitlines() if line.strip()]

    entries: list[dict[str, str]] = []
    endpoints: list[MetadataEndpoint] = []
    child_sitemaps: list[str] = []
    rejections: list[MetadataRejection] = []
    for kind, value in values[: settings.public_metadata_max_entries_per_document]:
        entry, endpoint, rejection = _candidate(project, document_url, value, kind, "sitemap")
        if rejection:
            rejections.append(rejection)
            continue
        if entry:
            entries.append(entry)
        if kind == "sitemap":
            child_sitemaps.append(urljoin(document_url, value))
        elif endpoint:
            endpoints.append(endpoint)
    return entries, endpoints, child_sitemaps, rejections


def _load_api_spec(body: str) -> dict:
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, RecursionError):
        try:
            value = yaml.load(body, Loader=_NoAliasSafeLoader)
        except (yaml.YAMLError, RecursionError) as exc:
            raise ValueError("API specification was not valid JSON or safe YAML.") from exc
    if not isinstance(value, dict):
        raise ValueError("API specification root must be an object.")
    is_openapi = str(value.get("openapi", "")).startswith("3.")
    is_swagger = str(value.get("swagger", "")) == "2.0"
    if not (is_openapi or is_swagger) or not isinstance(value.get("paths"), dict):
        raise ValueError("Document is not a supported OpenAPI 3.x or Swagger 2.0 specification.")
    return value


def _resolve_local_reference(spec: dict, value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    reference = value.get("$ref")
    if not isinstance(reference, str) or not reference.startswith("#/"):
        return value
    current: object = spec
    for part in reference[2:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current if isinstance(current, dict) else None


def _expand_server_url(server: object, document_url: str) -> str | None:
    if not isinstance(server, dict) or not isinstance(server.get("url"), str):
        return None
    value = server["url"]
    variables = server.get("variables") if isinstance(server.get("variables"), dict) else {}
    for name, definition in variables.items():
        default = definition.get("default") if isinstance(definition, dict) else None
        if default is not None:
            value = value.replace("{" + str(name) + "}", str(default))
    if "{" in value or "}" in value:
        return None
    return urljoin(document_url, value)


def _swagger_base(spec: dict, document_url: str) -> str:
    document = urlsplit(document_url)
    schemes = [value for value in spec.get("schemes", []) if value in {"http", "https"}]
    scheme = document.scheme if document.scheme in schemes or not schemes else schemes[0]
    host = spec.get("host") if isinstance(spec.get("host"), str) else document.netloc
    base_path = spec.get("basePath") if isinstance(spec.get("basePath"), str) else "/"
    return urlunsplit((scheme, host, base_path.rstrip("/") + "/", "", ""))


def _operation_bases(spec: dict, path_item: dict, operation: dict, document_url: str) -> list[str]:
    if str(spec.get("swagger", "")) == "2.0":
        return [_swagger_base(spec, document_url)]
    servers = operation.get("servers") or path_item.get("servers") or spec.get("servers") or [{"url": "/"}]
    if not isinstance(servers, list):
        return []
    return [value for server in servers[:20] if (value := _expand_server_url(server, document_url))]


def _schema_type(spec: dict, raw_schema: object) -> str | None:
    schema = _resolve_local_reference(spec, raw_schema)
    if not schema:
        return None
    value = schema.get("type")
    if isinstance(value, list):
        value = next((item for item in value if item != "null"), None)
    if isinstance(value, str):
        return value
    if isinstance(schema.get("properties"), dict):
        return "object"
    return None


def _operation_parameters(spec: dict, path_item: dict, operation: dict) -> list[dict]:
    parameters: list[dict] = []
    combined = []
    for source in (path_item.get("parameters"), operation.get("parameters")):
        if isinstance(source, list):
            combined.extend(source[:200])
    for raw in combined:
        parameter = _resolve_local_reference(spec, raw)
        if not parameter:
            continue
        name, location = parameter.get("name"), parameter.get("in")
        if isinstance(name, str) and isinstance(location, str) and location in {
            "query", "path", "header", "cookie", "body", "formData"
        }:
            detail = {
                "name": name[:255],
                "in": location,
                "required": bool(parameter.get("required", location == "path")),
            }
            schema_type = _schema_type(spec, parameter.get("schema") or parameter)
            if schema_type:
                detail["schema_type"] = schema_type
            parameters.append(detail)
    unique = {(item["in"], item["name"]): item for item in parameters}
    return sorted(unique.values(), key=lambda item: (item["in"], item["name"]))[:200]


def _placeholder_from_schema(
    spec: dict,
    raw_schema: object,
    *,
    depth: int = 0,
    seen_refs: frozenset[str] = frozenset(),
    budget: list[int] | None = None,
) -> object:
    if budget is None:
        budget = [200]
    if budget[0] <= 0:
        return "<truncated>"
    budget[0] -= 1
    if depth >= 5 or not isinstance(raw_schema, dict):
        return "<value>"
    reference = raw_schema.get("$ref")
    if isinstance(reference, str):
        if not reference.startswith("#/") or reference in seen_refs:
            return "<value>"
        resolved = _resolve_local_reference(spec, raw_schema)
        if not resolved:
            return "<value>"
        return _placeholder_from_schema(
            spec, resolved, depth=depth + 1, seen_refs=seen_refs | {reference}, budget=budget
        )
    schema = raw_schema
    for composition in ("oneOf", "anyOf"):
        options = schema.get(composition)
        if isinstance(options, list) and options:
            return _placeholder_from_schema(spec, options[0], depth=depth + 1, seen_refs=seen_refs, budget=budget)
    all_of = schema.get("allOf")
    if isinstance(all_of, list) and all_of:
        merged: dict = {}
        for part in all_of[:10]:
            value = _placeholder_from_schema(spec, part, depth=depth + 1, seen_refs=seen_refs, budget=budget)
            if isinstance(value, dict):
                merged.update(value)
        return merged or "<value>"

    schema_type = _schema_type(spec, schema)
    if schema_type == "object":
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        if properties:
            return {
                str(name)[:255]: _placeholder_from_schema(
                    spec, child, depth=depth + 1, seen_refs=seen_refs, budget=budget
                )
                for name, child in list(properties.items())[:20]
            }
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            return {"<key>": _placeholder_from_schema(
                spec, additional, depth=depth + 1, seen_refs=seen_refs, budget=budget
            )}
        return {}
    if schema_type == "array":
        return [_placeholder_from_schema(
            spec, schema.get("items", {}), depth=depth + 1, seen_refs=seen_refs, budget=budget
        )]
    if schema_type in {"integer", "number"}:
        return 0
    if schema_type == "boolean":
        return False
    if schema_type == "null":
        return None
    value_format = schema.get("format")
    if value_format == "email":
        return "user@example.test"
    if value_format == "uuid":
        return "00000000-0000-0000-0000-000000000000"
    if value_format in {"password", "binary", "byte"}:
        return "[REQUIRED]"
    if isinstance(schema.get("enum"), list):
        return "<choose documented value>"
    return "<string>"


def _security_requirements(spec: dict, operation: dict) -> list[dict]:
    raw = operation["security"] if "security" in operation else spec.get("security", [])
    if not isinstance(raw, list):
        return []
    requirements: list[dict] = []
    for requirement in raw[:20]:
        if not isinstance(requirement, dict):
            continue
        requirements.append({
            str(name)[:255]: [str(scope)[:255] for scope in scopes[:20]] if isinstance(scopes, list) else []
            for name, scopes in requirement.items()
        })
    return requirements


def _request_body_intelligence(
    spec: dict,
    path_item: dict,
    operation: dict,
    parameters: list[dict],
) -> tuple[list[str], dict]:
    content_types: list[str] = []
    schema: object = None
    swagger = str(spec.get("swagger", "")) == "2.0"
    if swagger:
        consumes = operation.get("consumes") or spec.get("consumes") or []
        if isinstance(consumes, list):
            content_types = sorted({str(value)[:255] for value in consumes if isinstance(value, str)})[:50]
        raw_parameters = []
        for source in (path_item.get("parameters"), operation.get("parameters")):
            if isinstance(source, list):
                raw_parameters.extend(source)
        for raw in raw_parameters:
            parameter = _resolve_local_reference(spec, raw)
            if parameter and parameter.get("in") == "body":
                schema = parameter.get("schema")
                break
    else:
        request_body = _resolve_local_reference(spec, operation.get("requestBody"))
        content = request_body.get("content") if request_body and isinstance(request_body.get("content"), dict) else {}
        content_types = sorted(str(value)[:255] for value in content)[:50]
        selected = next((value for value in content_types if value == "application/json" or value.endswith("+json")), None)
        selected = selected or (content_types[0] if content_types else None)
        media = content.get(selected) if selected else None
        schema = media.get("schema") if isinstance(media, dict) else None

    selected_type = next(
        (value for value in content_types if value == "application/json" or value.endswith("+json")),
        content_types[0] if content_types else None,
    )
    headers: dict[str, str] = {}
    manual_values = [
        f"{item['in']}:{item['name']}" for item in parameters
        if item.get("required") and item.get("in") in {"query", "path", "header", "cookie"}
    ]
    for item in parameters:
        if item.get("in") == "header" and item.get("required"):
            headers[item["name"]] = "[REQUIRED]"

    body: str | None = None
    if selected_type:
        manual_values.append("body")
        headers["Content-Type"] = selected_type
        if selected_type == "application/json" or selected_type.endswith("+json"):
            body = json.dumps(_placeholder_from_schema(spec, schema or {}), indent=2)
        elif selected_type == "application/x-www-form-urlencoded":
            fields = {
                item["name"]: "[REQUIRED]" if item.get("required") else "<optional>"
                for item in parameters if item.get("in") == "formData"
            }
            body = urlencode(fields)
        else:
            body = f"[BODY REQUIRED: {selected_type}]"
    return content_types, {
        "headers": headers,
        "body": body,
        "requires_manual_values": manual_values,
        "inert_placeholders": True,
    }


def parse_openapi(
    project: Project,
    document_url: str,
    body: str,
) -> tuple[list[dict[str, str]], list[MetadataEndpoint], list[MetadataRejection]]:
    spec = _load_api_spec(body)
    entries: list[dict[str, str]] = []
    endpoints: list[MetadataEndpoint] = []
    rejections: list[MetadataRejection] = []
    limit = settings.public_metadata_max_entries_per_document

    for path, raw_path_item in spec["paths"].items():
        if len(entries) >= limit or not isinstance(path, str) or not path.startswith("/"):
            continue
        path_item = _resolve_local_reference(spec, raw_path_item)
        if not path_item:
            continue
        for method, raw_operation in path_item.items():
            if len(entries) >= limit or method.lower() not in _HTTP_METHODS or not isinstance(raw_operation, dict):
                continue
            operation = raw_operation
            parameters = _operation_parameters(spec, path_item, operation)
            query_names = sorted(item["name"] for item in parameters if item["in"] == "query")
            parameter_summary = ", ".join(f"{item['in']}:{item['name']}" for item in parameters)
            content_types, request_template = _request_body_intelligence(spec, path_item, operation, parameters)
            security = _security_requirements(spec, operation)
            raw_tags = operation.get("tags") if isinstance(operation.get("tags"), list) else []
            tags = sorted({str(value)[:100] for value in raw_tags[:50] if isinstance(value, str)})
            operation_id = operation.get("operationId") if isinstance(operation.get("operationId"), str) else None
            summary = operation.get("summary") if isinstance(operation.get("summary"), str) else None
            for base in _operation_bases(spec, path_item, operation, document_url):
                endpoint_url = urljoin(base.rstrip("/") + "/", path.lstrip("/"))
                if query_names:
                    endpoint_url += "?" + urlencode([(name, "") for name in query_names])
                endpoint, reason = sanitize_endpoint_url(
                    project, endpoint_url, allow_destructive_path=True
                )
                if endpoint is None:
                    rejections.append(MetadataRejection(
                        redact_url_for_log(endpoint_url), reason or "API operation URL rejected.", "openapi"
                    ))
                    continue
                verb = method.upper()
                entry = {"type": "operation", "value": f"{verb} {endpoint.url}"}
                if parameter_summary:
                    entry["parameters"] = parameter_summary
                entries.append(entry)
                endpoints.append(MetadataEndpoint(
                    endpoint=endpoint,
                    source="openapi",
                    method=verb,
                    parameter_details=parameters,
                    request_body_content_types=content_types,
                    security_requirements=security,
                    tags=tags,
                    operation_id=operation_id[:255] if operation_id else None,
                    summary=summary[:1000] if summary else None,
                    deprecated=bool(operation.get("deprecated", False)),
                    request_template=request_template,
                ))
                if len(entries) >= limit:
                    break
    return entries, endpoints, rejections


def _base_roots(urls: list[str]) -> list[str]:
    roots: dict[str, str] = {}
    for value in urls:
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            continue
        port = parts.port
        netloc = parts.hostname.lower() if port is None else f"{parts.hostname.lower()}:{port}"
        root = urlunsplit((parts.scheme.lower(), netloc, "/", "", ""))
        current = roots.get(parts.hostname.lower())
        if current is None or (root.startswith("https://") and not current.startswith("https://")):
            roots[parts.hostname.lower()] = root
    return sorted(roots.values())


def _looks_like_api_spec(url: str) -> bool:
    path = urlsplit(url).path.lower().rstrip("/")
    return path.endswith(("openapi.json", "swagger.json", "openapi.yaml", "swagger.yaml")) or path.endswith("/v3/api-docs")


async def discover_public_metadata(project: Project, live_urls: list[str]) -> PublicMetadataDiscovery:
    result = PublicMetadataDiscovery()
    if not settings.public_metadata_enabled:
        return result

    queue: deque[tuple[str, str, int]] = deque()
    for root in _base_roots(live_urls):
        queue.append((urljoin(root, "/robots.txt"), "robots", 0))
        queue.append((urljoin(root, "/sitemap.xml"), "sitemap", 0))
        if settings.api_spec_discovery_enabled:
            queue.extend((urljoin(root, path), "openapi", 0) for path in _OPENAPI_PATHS)

    seen: set[str] = set()
    documents_by_host: dict[str, int] = defaultdict(int)
    async with httpx.AsyncClient(
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": settings.http_user_agent},
    ) as client:
        while queue:
            raw_url, kind, depth = queue.popleft()
            key = raw_url.split("#", 1)[0]
            if key in seen:
                continue
            seen.add(key)
            host = (urlsplit(raw_url).hostname or "").lower()
            if documents_by_host[host] >= settings.public_metadata_max_documents_per_host:
                continue

            safe, reason = sanitize_endpoint_url(project, raw_url)
            if safe is None:
                result.rejections.append(MetadataRejection(redact_url_for_log(raw_url), reason or "Metadata URL rejected.", kind))
                continue
            documents_by_host[host] += 1
            while not rate_limiter.allow(project.id or 0, project.rate_limit_rps):
                await asyncio.sleep(1.0 / max(project.rate_limit_rps, 0.1))

            document = MetadataDocument(url=safe.url, kind=kind)
            try:
                byte_limit = min(settings.public_metadata_max_response_bytes, 512_000) if kind == "robots" else settings.public_metadata_max_response_bytes
                response = await request_with_safe_redirects(
                    client, project, "GET", raw_url, max_response_bytes=byte_limit
                )
                document.status_code = response.status_code
                document.content_type = response.headers.get("content-type", "")[:255] or None
                if response.status_code != 200:
                    if kind != "openapi":
                        result.documents.append(document)
                    continue
                document.content_sha256 = hashlib.sha256(response.content).hexdigest()
                text = response.text
                if kind == "robots":
                    entries, endpoints, children, rejections = parse_robots(project, raw_url, text)
                elif kind == "sitemap":
                    entries, endpoints, children, rejections = parse_sitemap(project, raw_url, text)
                else:
                    entries, endpoints, rejections = parse_openapi(project, raw_url, text)
                    children = []
                document.entries = entries
                result.endpoints.extend(endpoints)
                result.rejections.extend(rejections)
                if depth < 2:
                    queue.extend((child, "sitemap", depth + 1) for child in children)
                if settings.api_spec_discovery_enabled and kind in {"robots", "sitemap"}:
                    queue.extend(
                        (item.endpoint.url, "openapi", 0)
                        for item in endpoints
                        if _looks_like_api_spec(item.endpoint.url)
                    )
            except (OutboundSafetyError, httpx.HTTPError, ValueError) as exc:
                if kind == "openapi":
                    continue
                document.error = str(exc)[:1000]
            result.documents.append(document)
    return result
