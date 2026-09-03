from pydantic import BaseModel


class EndpointOut(BaseModel):
    pattern: str
    category: str
    methods: list[str]
    sample_urls: list[str]
    sources: list[str]
    query_parameters: list[str]
    tags: list[str]
    security_schemes: list[str]
    deprecated_methods: list[str]
    operation_summaries: list[str]
    has_object_identifier: bool
    interesting_score: int
    reasons: list[str]
    suggested_investigation: str


class ApiMapOut(BaseModel):
    categories: dict[str, list[EndpointOut]]
    total_endpoints: int
