from app.api_mapper.categorize import (
    categorize_path,
    has_object_identifier,
    normalize_path,
    score_endpoint,
)
from app.api_mapper.service import build_api_map
from app.core.database import Base
from app.projects.models import Project
from app.surface.models import DiscoveredEndpoint
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_normalize_path_collapses_numeric_id():
    assert normalize_path("/api/orders/123") == "/api/orders/{id}"


def test_normalize_path_collapses_uuid():
    assert normalize_path("/api/users/550e8400-e29b-41d4-a716-446655440000") == "/api/users/{id}"


def test_normalize_path_leaves_existing_placeholder():
    assert normalize_path("/api/users/{id}") == "/api/users/{id}"


def test_normalize_path_collapses_colon_param():
    assert normalize_path("/api/files/:fileId") == "/api/files/{id}"


def test_normalize_path_leaves_static_segments_alone():
    assert normalize_path("/api/orders") == "/api/orders"


def test_categorize_path_matches_known_categories():
    assert categorize_path("/api/login") == "Authentication"
    assert categorize_path("/api/orders/{id}") == "Orders"
    assert categorize_path("/graphql") == "GraphQL"
    assert categorize_path("/api/widgets") == "Other"


def test_score_endpoint_with_object_id_and_json_scores_high():
    score, reasons = score_endpoint("/api/users/{id}", "Users", seen_json=True)
    assert score >= 60
    assert any("object identifier" in r for r in reasons)
    assert any("JSON" in r for r in reasons)


def test_score_endpoint_plain_path_has_fallback_reason():
    score, reasons = score_endpoint("/health", "Other", seen_json=False)
    assert score == 0
    assert reasons == ["No strong signals yet - inspect it to learn more."]


def test_has_object_identifier():
    assert has_object_identifier("/api/orders/{id}") is True
    assert has_object_identifier("/api/orders") is False


def test_api_map_includes_crawler_parameters_and_json_signal():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = Project(
            name="Mapper Test", target="example.com", allowed_domains=["example.com"],
            allowed_subdomains=[], excluded_assets=[], rate_limit_rps=1.0,
        )
        db.add(project)
        db.flush()
        db.add(DiscoveredEndpoint(
            project_id=project.id,
            url="https://api.example.com/api/orders/42?expand=items",
            normalized_url="https://api.example.com/api/orders/42?expand=",
            hostname="api.example.com", path="/api/orders/42", method="GET",
            query_parameters=["expand"], source="katana", status_code=200,
            content_type="application/json",
        ))
        db.add(DiscoveredEndpoint(
            project_id=project.id,
            url="https://api.example.com/api/orders/42?expand=",
            normalized_url="https://api.example.com/api/orders/42?expand=",
            hostname="api.example.com", path="/api/orders/42", method="POST",
            query_parameters=["expand"], source="openapi", tags=["Orders"],
            security_requirements=[{"bearerAuth": []}], deprecated=True,
            summary="Update an order",
        ))
        db.commit()

        result = build_api_map(db, project.id)

    endpoint = result["Orders"][0]
    assert endpoint["pattern"] == "/api/orders/{id}"
    assert endpoint["methods"] == ["GET", "POST"]
    assert endpoint["sources"] == ["katana", "openapi"]
    assert endpoint["query_parameters"] == ["expand"]
    assert endpoint["tags"] == ["Orders"]
    assert endpoint["security_schemes"] == ["bearerAuth"]
    assert endpoint["deprecated_methods"] == ["POST"]
    assert endpoint["operation_summaries"] == ["POST: Update an order"]
    assert any("Observed query parameters" in reason for reason in endpoint["reasons"])
    assert any("declares authentication" in reason for reason in endpoint["reasons"])
    assert endpoint["interesting_score"] >= 70
