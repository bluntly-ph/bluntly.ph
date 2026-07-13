"""AI critique service (M1, ADR-013).

Provider-abstracted so the backend is provider-agnostic (per the product owner:
this is a backend concern the frontend calls). `AI_PROVIDER` selects the impl:

  * "stub"   — deterministic, no network, no key (default; M1 runs out of the box).
  * "claude" — Anthropic Messages API (default model claude-haiku-4-5; swappable
               to claude-opus-4-8 via AI_MODEL for higher quality).
  * "openai" — OpenAI Chat Completions (lazy import; clear error if not installed).

A provider requiring a key that isn't configured raises a 503 problem+json so the
frontend gets an actionable error instead of a crash.
"""

from __future__ import annotations

import json
import re
from typing import Protocol

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.schemas.ai import CritiqueResponse

log = get_logger("ai.critique")

_SYSTEM = (
    "You are an editorial critic for a verified product-review platform. "
    "Assess a draft product review for helpfulness, specificity, balance, and "
    "evidence. Be direct and constructive. Respond with ONLY a JSON object of the "
    "form: {\"quality_score\": <int 0-100>, \"summary\": <string>, "
    "\"strengths\": [<string>...], \"weaknesses\": [<string>...], "
    "\"suggestions\": [<string>...]}. No prose outside the JSON."
)


def _build_user_prompt(title: str | None, text: str) -> str:
    header = f"Title: {title}\n\n" if title else ""
    return f"{header}Review draft:\n{text}"


def _coerce(data: dict, provider: str, model: str) -> CritiqueResponse:
    score = int(max(0, min(100, data.get("quality_score", 0))))
    return CritiqueResponse(
        provider=provider, model=model, quality_score=score,
        summary=str(data.get("summary", "")).strip(),
        strengths=[str(s) for s in data.get("strengths", [])][:10],
        weaknesses=[str(s) for s in data.get("weaknesses", [])][:10],
        suggestions=[str(s) for s in data.get("suggestions", [])][:10],
    )


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


class AICritiqueProvider(Protocol):
    name: str

    def critique(self, title: str | None, text: str) -> CritiqueResponse: ...


class StubProvider:
    """Deterministic heuristic critique — no network, no key."""

    name = "stub"

    def critique(self, title: str | None, text: str) -> CritiqueResponse:
        words = text.split()
        wc = len(words)
        has_pros = any(w in text.lower() for w in ("pro", "good", "like", "love"))
        has_cons = any(w in text.lower() for w in ("con", "bad", "issue", "but", "however"))
        score = min(100, 30 + min(40, wc // 5) + (15 if has_pros else 0) + (15 if has_cons else 0))
        strengths, weaknesses, suggestions = [], [], []
        (strengths if wc >= 40 else weaknesses).append(
            "Sufficient detail." if wc >= 40 else "Very short — add specifics.")
        (strengths if has_pros and has_cons else weaknesses).append(
            "Balanced pros and cons." if has_pros and has_cons
            else "Mention both upsides and downsides.")
        if not has_cons:
            suggestions.append("Add at least one honest drawback.")
        suggestions.append("Include what you used it for and for how long.")
        return CritiqueResponse(
            provider=self.name, model="heuristic-v1", quality_score=score,
            summary=f"Heuristic assessment of a {wc}-word draft.",
            strengths=strengths, weaknesses=weaknesses, suggestions=suggestions)


class ClaudeProvider:
    name = "claude"

    def critique(self, title: str | None, text: str) -> CritiqueResponse:
        if not settings.anthropic_api_key:
            raise AppError("AI critique is not configured (ANTHROPIC_API_KEY missing).",
                           code="ai_not_configured", status_code=503)
        try:
            from anthropic import Anthropic
        except ImportError as exc:  # pragma: no cover
            raise AppError("anthropic SDK not installed.", code="ai_provider_missing",
                           status_code=503) from exc
        client = Anthropic(api_key=settings.anthropic_api_key)
        try:
            resp = client.messages.create(
                model=settings.ai_model,
                max_tokens=settings.ai_max_tokens,
                system=_SYSTEM,
                messages=[{"role": "user", "content": _build_user_prompt(title, text)}],
            )
        except Exception as exc:  # noqa: BLE001
            log.info("claude critique failed", extra={"extra_fields": {"error": str(exc)}})
            raise AppError("AI provider request failed.", code="ai_request_failed",
                           status_code=502) from exc
        raw = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
        try:
            return _coerce(_parse_json(raw), self.name, settings.ai_model)
        except (json.JSONDecodeError, ValueError) as exc:
            raise AppError("AI provider returned unparseable output.",
                           code="ai_bad_output", status_code=502) from exc


class OpenAIProvider:
    name = "openai"

    def critique(self, title: str | None, text: str) -> CritiqueResponse:
        if not settings.openai_api_key:
            raise AppError("AI critique is not configured (OPENAI_API_KEY missing).",
                           code="ai_not_configured", status_code=503)
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AppError("openai SDK not installed; add it to requirements to use this provider.",
                           code="ai_provider_missing", status_code=503) from exc
        client = OpenAI(api_key=settings.openai_api_key)
        try:
            resp = client.chat.completions.create(
                model=settings.ai_model,
                messages=[{"role": "system", "content": _SYSTEM},
                          {"role": "user", "content": _build_user_prompt(title, text)}],
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content or "{}"
        except Exception as exc:  # noqa: BLE001
            raise AppError("AI provider request failed.", code="ai_request_failed",
                           status_code=502) from exc
        try:
            return _coerce(_parse_json(raw), self.name, settings.ai_model)
        except (json.JSONDecodeError, ValueError) as exc:
            raise AppError("AI provider returned unparseable output.",
                           code="ai_bad_output", status_code=502) from exc


_PROVIDERS = {"stub": StubProvider, "claude": ClaudeProvider, "openai": OpenAIProvider}


def get_provider() -> AICritiqueProvider:
    impl = _PROVIDERS.get(settings.ai_provider.lower())
    if impl is None:
        raise AppError(f"Unknown AI provider '{settings.ai_provider}'.",
                       code="ai_provider_unknown", status_code=500)
    return impl()
