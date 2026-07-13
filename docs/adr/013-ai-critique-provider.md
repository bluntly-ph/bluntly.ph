# ADR-013: AI critique provider abstraction

- **Status:** Accepted (M1)
- **Context:** M1 requires "basic AI critique integration via OpenAI or Claude API."
  The product owner framed it as a backend concern the frontend calls, and was
  unsure it must ship enabled.

## Decision
An abstracted service (`app/services/ai_critique.py`) with a provider interface and
three implementations, selected by `AI_PROVIDER`:
- **`stub`** (default) — deterministic heuristic critique, no network, no key. M1
  runs and is testable out of the box.
- **`claude`** — Anthropic Messages API (`client.messages.create`), default model
  `claude-haiku-4-5` (cost/speed-appropriate for high-volume critique; swap to
  `claude-opus-4-8` via `AI_MODEL` for higher quality). No `temperature` (removed on
  current models). Requires `ANTHROPIC_API_KEY`.
- **`openai`** — OpenAI Chat Completions, lazy-imported; requires `OPENAI_API_KEY`
  and the `openai` package.

Endpoints: `POST /ai/critique` (ad-hoc text) and `POST /reviews/{id}/critique`
(stored review). A provider missing its key returns **503 problem+json**
(`ai_not_configured`) so the frontend gets an actionable error, never a crash.
Output is a structured `CritiqueResponse` (quality_score, summary, strengths,
weaknesses, suggestions).

## Consequences
The backend is provider-agnostic and enabled-by-configuration. Swapping providers or
models is an env change, not a code change.
