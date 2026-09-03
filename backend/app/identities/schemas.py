from datetime import datetime

from pydantic import BaseModel, Field


class IdentityProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    headers: dict[str, str] = Field(min_length=1, max_length=20)


class IdentityProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    headers: dict[str, str] | None = Field(default=None, min_length=1, max_length=20)
    enabled: bool | None = None


class IdentityProfileOut(BaseModel):
    id: int
    project_id: int
    name: str
    description: str
    header_names: list[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime
