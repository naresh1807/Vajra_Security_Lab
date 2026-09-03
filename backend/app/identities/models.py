from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.encrypted_types import EncryptedJSON


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IdentityProfile(Base):
    __tablename__ = "identity_profiles"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_identity_project_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    identity_key: Mapped[str] = mapped_column(String(64), unique=True, default=lambda: secrets.token_urlsafe(24))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    secret_headers: Mapped[dict[str, str]] = mapped_column(EncryptedJSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    project = relationship("Project", back_populates="identity_profiles")
    transactions = relationship("HttpTransaction", back_populates="identity_profile", passive_deletes=True)
