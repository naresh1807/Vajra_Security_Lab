from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.encrypted_types import EncryptedJSON, EncryptedText


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HttpTransaction(Base):
    """A single manually-sent request/response pair (Vajra HTTP Inspector, Section 12).

    Every transaction here already passed Vajra ScopeGuard and the
    project's rate limiter before being sent - see http/service.py.
    """

    __tablename__ = "http_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    identity_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("identity_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Immutable attribution survives profile renames/deletion and lets Diff
    # distinguish controlled accounts without comparing their secret values.
    identity_profile_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_profile_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    profile_header_names: Mapped[list[str]] = mapped_column(JSON, default=list)

    method: Mapped[str] = mapped_column(String(10))
    url: Mapped[str] = mapped_column(String(2000))
    request_headers: Mapped[dict] = mapped_column(EncryptedJSON, default=dict)
    request_body: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)

    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_headers: Mapped[dict] = mapped_column(EncryptedJSON, default=dict)
    # Raw Set-Cookie values, one per cookie - a plain header dict collapses
    # duplicates to the last one, which would silently break cookie analysis
    # on any response setting more than one cookie.
    response_cookies: Mapped[list[str]] = mapped_column(EncryptedJSON, default=list)
    response_body: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    response_body_truncated: Mapped[bool] = mapped_column(default=False)
    response_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timing_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    technologies: Mapped[list[str]] = mapped_column(JSON, default=list)
    interesting_indicators: Mapped[list[str]] = mapped_column(JSON, default=list)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project = relationship("Project", back_populates="http_transactions")
    identity_profile = relationship("IdentityProfile", back_populates="transactions")
