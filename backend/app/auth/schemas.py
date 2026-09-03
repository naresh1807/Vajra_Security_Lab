from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Enter a valid email address.")
        return value


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip_address: str
    user_agent: str
    current: bool


class AuthEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_type: str
    success: bool
    ip_address: str
    created_at: datetime
