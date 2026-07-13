"""Shared response schemas (feed the governed OpenAPI contract)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    product_id: str
    version: str
    timestamp: datetime


class Problem(BaseModel):
    """RFC 9457 problem document — the single error schema for the API."""

    type: str = Field(examples=["https://bluntly.ph/problems/not_found"])
    title: str
    status: int
    detail: str
    instance: str
    code: str


class CurrentUserResponse(BaseModel):
    id: str
    email: str | None = None
    authenticated: bool = True
