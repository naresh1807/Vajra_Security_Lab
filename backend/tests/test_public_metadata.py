import json

import pytest

from app.analyzer.checks import Classification
from app.analyzer.metadata import analyze_public_metadata
from app.core.database import Base
from app.projects.models import Project
from app.surface.metadata import MetadataDocument, PublicMetadataDiscovery, parse_openapi, parse_robots, parse_sitemap
from app.surface.models import DiscoveredEndpoint, PublicMetadataDocument
from app.surface.service import store_public_metadata
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def _project() -> Project:
    return Project(
        name="Metadata Test",
        target="example.com",
        allowed_domains=["example.com"],
        allowed_subdomains=[],
        excluded_assets=[],
        rate_limit_rps=10.0,
    )


def test_robots_parser_collects_safe_paths_and_declared_sitemaps():
    entries, endpoints, sitemaps, rejections = parse_robots(
        _project(),
        "https://example.com/robots.txt",
        """
        User-agent: *
        Disallow: /admin
        Allow: /public?page=1
        Disallow: /search/*
        Sitemap: https://example.com/maps/main.xml
        Sitemap: https://outside.test/sitemap.xml
        """,
    )

    assert [entry["type"] for entry in entries] == ["disallow", "allow", "disallow", "sitemap"]
    assert {item.endpoint.path for item in endpoints} == {"/admin", "/public", "/maps/main.xml"}
    assert sitemaps == ["https://example.com/maps/main.xml"]
    assert len(rejections) == 1
    assert "ScopeGuard" in rejections[0].reason


def test_robots_parser_redacts_secret_query_values_before_evidence_storage():
    entries, _, _, _ = parse_robots(
        _project(), "https://example.com/robots.txt", "Disallow: /private?token=raw-secret"
    )

    assert entries[0]["value"] == "https://example.com/private?token=%5BREDACTED%5D"
    assert "raw-secret" not in str(entries)


def test_sitemap_parser_supports_indexes_and_scope_rejects_children():
    body = """<?xml version="1.0"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://example.com/posts.xml</loc></sitemap>
      <sitemap><loc>https://outside.test/private.xml</loc></sitemap>
    </sitemapindex>"""

    entries, endpoints, children, rejections = parse_sitemap(
        _project(), "https://example.com/sitemap.xml", body
    )

    assert entries == [{"type": "sitemap", "value": "https://example.com/posts.xml"}]
    assert endpoints == []
    assert children == ["https://example.com/posts.xml"]
    assert len(rejections) == 1


def test_sitemap_parser_extracts_urls_without_fetching_them():
    body = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/api/orders/42?expand=items</loc></url>
      <url><loc>https://example.com/logout</loc></url>
    </urlset>"""

    entries, endpoints, children, rejections = parse_sitemap(
        _project(), "https://example.com/sitemap.xml", body
    )

    assert len(entries) == 1
    assert len(endpoints) == 1
    assert endpoints[0].endpoint.query_parameters == ["expand"]
    assert children == []
    assert len(rejections) == 1
    assert "destructive" in rejections[0].reason.lower()


def test_sitemap_parser_rejects_entity_declarations():
    with pytest.raises(ValueError, match="entities"):
        parse_sitemap(
            _project(),
            "https://example.com/sitemap.xml",
            '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><urlset>&xxe;</urlset>',
        )


def test_public_metadata_analyzer_marks_sensitive_names_as_needs_review_only():
    document = PublicMetadataDocument(
        project_id=1,
        url="https://example.com/robots.txt",
        kind="robots",
        status_code=200,
        entries=[{"type": "disallow", "value": "https://example.com/internal/admin"}],
    )

    finding = analyze_public_metadata(document)[0]

    assert finding.classification == Classification.NEEDS_REVIEW
    assert "does not prove" in finding.description
    assert finding.evidence == ["https://example.com/internal/admin"]


def test_metadata_storage_upserts_documents_and_endpoint_inventory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project()
        db.add(project)
        db.flush()
        entries, endpoints, _, _ = parse_robots(
            project, "https://example.com/robots.txt", "Disallow: /admin"
        )
        discovery = PublicMetadataDiscovery(
            documents=[MetadataDocument(
                url="https://example.com/robots.txt",
                kind="robots",
                status_code=200,
                content_type="text/plain",
                content_sha256="a" * 64,
                entries=entries,
            )],
            endpoints=endpoints,
        )

        assert store_public_metadata(db, project.id, discovery) == (1, 1, 0)
        assert store_public_metadata(db, project.id, discovery) == (0, 0, 0)
        assert db.query(PublicMetadataDocument).count() == 1
        endpoint = db.query(DiscoveredEndpoint).one()
        assert endpoint.source == "robots"
        assert endpoint.path == "/admin"


def test_openapi_parser_retains_distinct_methods_and_query_parameter_names():
    specification = {
        "openapi": "3.1.0",
        "servers": [{"url": "https://api.example.com/v1"}],
        "paths": {
            "/users/{id}": {
                "parameters": [{"name": "id", "in": "path", "required": True}],
                "get": {"responses": {"200": {"description": "ok"}}},
                "post": {
                    "operationId": "updateUser",
                    "summary": "Update a controlled user",
                    "tags": ["Users"],
                    "deprecated": True,
                    "parameters": [{"name": "X-Tenant", "in": "header", "required": True}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/UserUpdate"}
                            }
                        },
                    },
                    "responses": {"200": {"description": "ok"}},
                },
            },
            "/search": {
                "get": {
                    "parameters": [{"$ref": "#/components/parameters/SearchQuery"}],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/account/delete": {
                "delete": {"responses": {"204": {"description": "deleted"}}}
            },
        },
        "security": [{"bearerAuth": []}],
        "components": {
            "parameters": {"SearchQuery": {"name": "q", "in": "query"}},
            "schemas": {
                "UserUpdate": {
                    "type": "object",
                    "properties": {
                        "displayName": {"type": "string", "example": "real-user-name"},
                        "password": {"type": "string", "format": "password"},
                        "role": {"type": "string", "enum": ["admin", "member"]},
                    },
                }
            },
        },
    }

    entries, endpoints, rejections = parse_openapi(
        _project(), "https://example.com/openapi.json", json.dumps(specification)
    )

    assert {(item.method, item.endpoint.path) for item in endpoints} == {
        ("GET", "/v1/users/{id}"),
        ("POST", "/v1/users/{id}"),
        ("GET", "/v1/search"),
        ("DELETE", "/v1/account/delete"),
    }
    search = next(item for item in endpoints if item.endpoint.path.endswith("/search"))
    assert search.endpoint.query_parameters == ["q"]
    assert any(entry.get("parameters") == "query:q" for entry in entries)
    post = next(item for item in endpoints if item.method == "POST")
    assert post.operation_id == "updateUser"
    assert post.summary == "Update a controlled user"
    assert post.tags == ["Users"]
    assert post.deprecated is True
    assert post.security_requirements == [{"bearerAuth": []}]
    assert post.request_body_content_types == ["application/json"]
    assert post.request_template["headers"] == {
        "X-Tenant": "[REQUIRED]",
        "Content-Type": "application/json",
    }
    assert set(post.request_template["requires_manual_values"]) == {"path:id", "header:X-Tenant", "body"}
    assert "real-user-name" not in post.request_template["body"]
    assert '"displayName": "<string>"' in post.request_template["body"]
    assert '"password": "[REQUIRED]"' in post.request_template["body"]
    assert "admin" not in post.request_template["body"]
    assert rejections == []


def test_swagger_parser_uses_host_scheme_and_base_path():
    specification = {
        "swagger": "2.0",
        "host": "api.example.com",
        "basePath": "/v2",
        "schemes": ["https"],
        "consumes": ["application/json"],
        "security": [{"apiKey": []}],
        "paths": {"/pets": {"post": {"parameters": [
            {"name": "limit", "in": "query"},
            {"name": "pet", "in": "body", "required": True, "schema": {
                "type": "object", "properties": {"name": {"type": "string"}}
            }},
        ]}}},
    }

    _, endpoints, rejections = parse_openapi(
        _project(), "https://example.com/swagger.json", json.dumps(specification)
    )

    assert len(endpoints) == 1
    assert endpoints[0].endpoint.url == "https://api.example.com/v2/pets?limit="
    assert endpoints[0].method == "POST"
    assert endpoints[0].request_body_content_types == ["application/json"]
    assert '"name": "<string>"' in endpoints[0].request_template["body"]
    assert endpoints[0].security_requirements == [{"apiKey": []}]
    assert rejections == []


def test_openapi_parser_rejects_out_of_scope_servers_without_executing_operations():
    specification = {
        "openapi": "3.0.3",
        "servers": [{"url": "https://outside.test/api"}],
        "paths": {"/users": {"get": {}}},
    }

    entries, endpoints, rejections = parse_openapi(
        _project(), "https://example.com/openapi.json", json.dumps(specification)
    )

    assert entries == []
    assert endpoints == []
    assert len(rejections) == 1
    assert "ScopeGuard" in rejections[0].reason


def test_openapi_yaml_rejects_aliases():
    body = """
    openapi: 3.0.3
    paths: &shared
      /users:
        get: {}
    x-copy: *shared
    """

    with pytest.raises(ValueError, match="safe YAML"):
        parse_openapi(_project(), "https://example.com/openapi.yaml", body)


def test_storage_preserves_get_and_post_for_the_same_normalized_url():
    specification = {
        "openapi": "3.0.3",
        "security": [{"bearerAuth": []}],
        "paths": {"/users": {"get": {}, "post": {
            "operationId": "createUser",
            "summary": "Create a user",
            "tags": ["Users"],
            "requestBody": {"content": {"application/json": {"schema": {
                "type": "object", "properties": {"name": {"type": "string"}}
            }}}},
        }}},
    }
    _, endpoints, _ = parse_openapi(
        _project(), "https://example.com/openapi.json", json.dumps(specification)
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project()
        db.add(project)
        db.flush()
        discovery = PublicMetadataDiscovery(
            documents=[MetadataDocument(
                url="https://example.com/openapi.json", kind="openapi", status_code=200, entries=[]
            )],
            endpoints=endpoints,
        )

        assert store_public_metadata(db, project.id, discovery) == (2, 1, 0)
        assert {item.method for item in db.query(DiscoveredEndpoint).all()} == {"GET", "POST"}
        post = db.query(DiscoveredEndpoint).filter(DiscoveredEndpoint.method == "POST").one()
        assert post.operation_id == "createUser"
        assert post.summary == "Create a user"
        assert post.tags == ["Users"]
        assert post.security_requirements == [{"bearerAuth": []}]
        assert post.request_template["inert_placeholders"] is True


def test_public_metadata_analyzer_treats_api_spec_exposure_as_interesting_not_vulnerable():
    document = PublicMetadataDocument(
        project_id=1,
        url="https://example.com/openapi.json",
        kind="openapi",
        status_code=200,
        entries=[{"type": "operation", "value": "GET https://example.com/api/users"}],
    )

    finding = analyze_public_metadata(document)[0]

    assert finding.classification == Classification.INTERESTING
    assert "not a vulnerability" in finding.description
