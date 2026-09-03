from datetime import datetime

from pydantic import BaseModel


class HuntEventOut(BaseModel):
    id: str
    category: str
    title: str
    detail: str
    status: str
    occurred_at: datetime
    href: str | None = None


class HuntHistoryOut(BaseModel):
    events: list[HuntEventOut]
    total: int
    categories: dict[str, int]
