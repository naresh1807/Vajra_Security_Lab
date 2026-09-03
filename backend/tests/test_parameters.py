"""
Vajra Parameter Intelligence (Section 21).

Two layers: the pure classifier (name / schema type / value shape -> a
label and its review areas, never a vulnerability claim), and the
computed inventory that aggregates every parameter across HTTP history,
discovered endpoints, and JS routes without persisting a thing.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.http.models import HttpTransaction
from app.js_inspector.models import FindingType, JsFile, JsFinding
from app.parameters.categorize import classify_parameter, review_areas, value_shapes
from app.parameters.service import build_parameter_inventory
from app.projects.models import Project
from app.surface.models import DiscoveredEndpoint


# --- pure classifier -------------------------------------------------------

def test_numeric_id_name_is_a_numeric_object_identifier():
    assert classify_parameter("user_id", ["integer"], []) == "Numeric object identifier"
    assert classify_parameter("orderId", [], ["1024"]) == "Numeric object identifier"


def test_uuid_values_classify_as_uuid_identifier_even_without_id_name():
    assert (
        classify_parameter("ref", [], ["550e8400-e29b-41d4-a716-446655440000"])
        == "UUID object identifier"
    )


def test_credential_shaped_names_are_flagged_as_credentials():
    for name in ("access_token", "api_key", "password", "sessionId"):
        assert classify_parameter(name, [], []) == "Authentication or session credential"


def test_pagination_and_filter_controls():
    assert classify_parameter("page", [], []) == "Pagination or range control"
    assert classify_parameter("sort", [], []) == "Sorting, filtering or search control"


def test_redirect_and_file_names():
    assert classify_parameter("redirect_uri", [], []) == "Redirect or URL value"
    assert classify_parameter("filename", [], []) == "File or path value"


def test_boolean_by_type_or_value():
    assert classify_parameter("active", ["boolean"], []) == "Boolean flag"
    assert classify_parameter("include_deleted", [], ["true"]) == "Boolean flag"


def test_unremarkable_parameter_is_free_form():
    assert classify_parameter("comment", [], ["hello world"]) == "Free-form value"


def test_review_areas_are_lookup_and_never_empty():
    assert "Object-level authorization (BOLA / IDOR)" in review_areas("Numeric object identifier")
    assert review_areas("something unknown")  # falls back, still non-empty


def test_value_shapes_reports_shape_not_value():
    assert value_shapes(["42", "1007"]) == ["numeric"]
    assert value_shapes(["true", "false"]) == ["boolean-like"]
    assert value_shapes([]) == []


# --- computed inventory ---------------------------------------------------

def _project(db: Session) -> Project:
    project = Project(
        name="Params", target="example.com", allowed_domains=["example.com"],
        allowed_subdomains=[], excluded_assets=[], rate_limit_rps=1.0,
    )
    db.add(project)
    db.flush()
    return project


def test_inventory_aggregates_across_sources_and_ranks_identifiers_first():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project(db)

        # Spec-declared: a path id (required) and a query filter.
        db.add(DiscoveredEndpoint(
            project_id=project.id,
            url="https://api.example.com/api/orders/{id}",
            normalized_url="https://api.example.com/api/orders/{id}",
            hostname="api.example.com", path="/api/orders/{id}", method="GET",
            query_parameters=["status"], source="openapi",
            parameter_details=[
                {"name": "id", "in": "path", "required": True, "schema_type": "integer"},
                {"name": "status", "in": "query", "required": False, "schema_type": "string"},
            ],
        ))
        # Real request: reuses `id` on another endpoint + a secret query param.
        db.add(HttpTransaction(
            project_id=project.id, method="GET",
            url="https://api.example.com/api/invoices/7?id=7&api_key=SECRETVALUE123456",
        ))
        # JS route contributes a query name only.
        js = JsFile(project_id=project.id, url="https://example.com/app.js")
        db.add(js)
        db.flush()
        db.add(JsFinding(js_file_id=js.id, finding_type=FindingType.API_ROUTE,
                         value="/api/orders?status=open&page=2"))
        db.commit()

        inventory = build_parameter_inventory(db, project.id)

    by_name = {row["name"]: row for row in inventory}

    # `id` seen on two endpoints, from two sources, numeric -> identifier, ranked first.
    assert inventory[0]["name"] == "id"
    assert by_name["id"]["classification"] == "Numeric object identifier"
    assert by_name["id"]["observed_endpoint_count"] == 2
    assert set(by_name["id"]["sources"]) == {"openapi", "http"}
    assert by_name["id"]["required"] is True
    assert "Object-level authorization (BOLA / IDOR)" in by_name["id"]["review_areas"]

    assert by_name["status"]["classification"] == "Sorting, filtering or search control"
    assert set(by_name["status"]["sources"]) == {"openapi", "js"}

    # The credential-shaped param is classified but never surfaces a value shape.
    assert by_name["api_key"]["classification"] == "Authentication or session credential"
    assert by_name["api_key"]["value_shapes"] == []


def test_inventory_never_returns_raw_query_values():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project(db)
        db.add(HttpTransaction(
            project_id=project.id, method="GET",
            url="https://api.example.com/search?q=confidential-search-term&limit=50",
        ))
        db.commit()
        inventory = build_parameter_inventory(db, project.id)

    blob = repr(inventory)
    assert "confidential-search-term" not in blob
    q = next(row for row in inventory if row["name"] == "q")
    assert q["value_shapes"] == ["free text"]
    limit = next(row for row in inventory if row["name"] == "limit")
    assert limit["classification"] == "Pagination or range control"
    assert limit["value_shapes"] == ["numeric"]


def test_inventory_is_empty_for_a_project_with_no_data():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = _project(db)
        db.commit()
        assert build_parameter_inventory(db, project.id) == []
