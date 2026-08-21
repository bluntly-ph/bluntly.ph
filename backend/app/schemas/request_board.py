"""Request board schemas (M3 slice 9)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import RequestStatus
from app.schemas.urls import web_url_or_none


class RequestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(min_length=1)
    product_id: uuid.UUID | None = None
    # A marketplace link for humans. Stored, shown, NEVER fetched (no scraping).
    source_url: str | None = Field(default=None, max_length=2048)

    @field_validator("source_url")
    @classmethod
    def _only_web_source(cls, value: str | None) -> str | None:
        return web_url_or_none(value, field="Listing links")


class FulfillRequest(BaseModel):
    review_id: uuid.UUID


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: str | None = None
    requester_id: uuid.UUID
    product_id: uuid.UUID | None = None
    title: str
    details: str
    source_url: str | None = None
    status: RequestStatus
    fulfilled_by_review_id: uuid.UUID | None = None
    expires_at: datetime
    upvote_count: int = 0
    # Whether the requesting viewer has up-voted this (BUG-026). Not a column —
    # the route fills it in, because it is a fact about the viewer. Without it
    # the count survived a refresh but the highlight did not, and clicking again
    # sent a second POST that the unique constraint rejected, which read as the
    # button hanging.
    my_upvote: bool = False
    ai_validation: dict | None = None
    created_at: datetime
