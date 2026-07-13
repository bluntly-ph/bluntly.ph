# ADR-009: Rate limiting on auth/registration

- **Status:** Accepted (M0)
- **Context (Architecture §8 Q11, PRD §8):** The source spec has **no** rate
  limiting; registration flooding is only mitigated post-hoc by trust weighting.

## Decision
A **Redis fixed-window** limiter (`app/core/rate_limit.py`), applied as a
dependency on auth/registration-adjacent endpoints. Keyed by client IP
(`X-Forwarded-For` aware) + route bucket. Defaults (env-tunable):

- `AUTH_RATE_LIMIT_MAX = 10` requests
- `AUTH_RATE_LIMIT_WINDOW_SECONDS = 60`

Exceeding the window returns **429** as RFC 9457 problem+json with a
`retry_after_seconds` hint.

## Consequences
Cheap first-line defence using the Redis we already run. Fixed-window is
sufficient for launch; a sliding-window or token-bucket upgrade is a later option.
**CGNAT caveat (Q10):** many PH mobile users share carrier IPs, so IP-keyed limits
must stay generous to avoid false positives — the default is deliberately lenient
and the *fraud* IP-detection layer (M2) is advisory-only, never auto-blocking.
