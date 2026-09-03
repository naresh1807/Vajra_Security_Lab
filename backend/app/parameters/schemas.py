from pydantic import BaseModel


class ParameterInsight(BaseModel):
    name: str
    classification: str
    locations: list[str]
    sources: list[str]
    schema_types: list[str]
    required: bool
    observed_endpoint_count: int
    endpoints: list[str]
    value_shapes: list[str]
    review_areas: list[str]
    note: str


class ParameterInventoryOut(BaseModel):
    parameters: list[ParameterInsight]
    total_parameters: int
