"""AI critique schemas (M1)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CritiqueRequest(BaseModel):
    """Ad-hoc critique of arbitrary draft text (also reused for stored reviews)."""

    title: str | None = None
    text: str = Field(min_length=1)


class CritiqueResponse(BaseModel):
    provider: str
    model: str
    quality_score: int = Field(ge=0, le=100)
    summary: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
