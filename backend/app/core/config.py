"""Application settings, loaded from environment / repo-root .env.

Single source of truth for configuration. All secrets come from the environment;
nothing is hardcoded (see PRD §8 / Architecture §7 security notes).
"""

from __future__ import annotations

import json
from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

# Per-platform affiliate domain allowlist for referral-link validation (M2 slice 1).
# Override via AFFILIATE_ALLOWED_DOMAINS as JSON. A pasted link's host must equal or
# be a subdomain of one of these for the declared platform.
DEFAULT_AFFILIATE_DOMAINS: dict[str, list[str]] = {
    "shopee": ["s.shopee.ph", "shope.ee", "shopee.ph"],
    "lazada": ["s.lazada.com.ph", "c.lazada.com.ph", "lazada.com.ph"],
    "amazon": ["amzn.to", "amazon.com", "www.amazon.com"],
}


def _to_sqlalchemy_pg_url(raw: str) -> str:
    """Normalize any Postgres URL for SQLAlchemy + psycopg.

    - rewrites `postgres://` / `postgresql://` to `postgresql+psycopg://`
    - re-renders through SQLAlchemy so special characters in the password
      (e.g. `!`, `.`) are correctly percent-encoded regardless of how the raw
      Supabase connection string was pasted.
    """
    url = make_url(raw)
    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+psycopg")
    return url.render_as_string(hide_password=False)


class Settings(BaseSettings):
    # The frontend and backend share the repo-root .env; also read a local
    # backend/.env if present. Unknown keys (e.g. NEXT_PUBLIC_*) are ignored.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_env: str = "local"  # local | staging | production
    app_version: str = "0.1.0"
    product_id: str = "bluntly-ph"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    enable_docs: bool = True  # serve /docs, /redoc, /openapi.json

    # --- Database ---
    # Local default; overridden per-service in docker-compose.
    database_url: str = "postgresql+psycopg://bluntly:bluntly@localhost:5432/bluntly"
    # When true, runtime + Alembic target Supabase (below) instead of DATABASE_URL.
    use_supabase: bool = False
    db_sslmode: str = "require"  # applied to Supabase connections

    # --- Performance (engine pool + threadpool; see docs/PRODUCTION.md) ---
    # Connection budget = workers x (pool_size + max_overflow) + Celery.
    # Defaults: 2 x 20 + ~4 = 44. Keep this under the ceiling of whatever sits in
    # front of Postgres (the Supabase session pooler) — raise workers and pool
    # together, never one alone.
    db_pool_size: int = 10
    db_max_overflow: int = 10
    db_pool_timeout: int = 10       # fail fast instead of 30s pile-ups
    db_pool_recycle: int = 300      # safe for the Supabase session pooler
    # AnyIO threadpool ceiling = in-flight sync requests per process. Every sync
    # endpoint holds its DB session for the whole request (get_db), so admitting
    # more concurrent requests than the pool can serve adds no throughput — the
    # surplus just waits on the pool and 500s after db_pool_timeout.
    #
    # The M3 slice-14 load test proved this is not theoretical: at the old 40
    # tokens against a 10-connection pool, 100 users produced 40x "QueuePool
    # limit of size 5 overflow 5 reached" and 500s on *unrelated* endpoints —
    # one slow endpoint (the moderator queue, ~915ms of query time per page)
    # starved everything else. Keep tokens <= pool_size + max_overflow;
    # production_issues() enforces it.
    threadpool_tokens: int = 20

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Supabase ---
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    supabase_jwks_url: str = ""
    # Full Postgres connection string from the Supabase dashboard.
    # The direct string (db.<ref>.supabase.co) is IPv6-only; the session-pooler
    # string is IPv4 and preferred when set (works from IPv4 networks).
    supabase_connection_string: str = ""
    # Session mode (:5432) — used by ALEMBIC only. Caps at ~4 concurrent clients.
    supabase_connection_string_session_pooler: str = ""
    # Transaction mode (:6543) — used by the APP. Optional: derived from the
    # session-pooler string by switching the port when left blank.
    supabase_connection_string_transaction_pooler: str = ""

    # --- Security / rate limiting ---
    auth_rate_limit_max: int = 10
    auth_rate_limit_window_seconds: int = 60

    # --- Auth (FastAPI-native JWT/OAuth2 — ADR-010) ---
    jwt_secret: str = "dev-insecure-change-me"  # MUST be overridden in prod
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "bluntly-ph"
    access_token_expire_minutes: int = 60 * 24  # 24h

    # --- AI critique (ADR-013). provider: stub | claude | openai ---
    ai_provider: str = "stub"
    ai_model: str = "claude-haiku-4-5"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ai_max_tokens: int = 700

    # --- Referral / affiliate links (M2 slice 1) ---
    affiliate_allowed_domains: str = ""   # optional JSON override of the defaults
    earn_eligible_auto_queue: bool = True  # new reviews auto-enter the moderator queue

    # --- Community voting (M2 slice 2) — reuses the 60s fixed-window limiter ---
    vote_rate_limit_max: int = 30

    # Reporting is rarer than voting and more abusable (one account carpet-
    # reporting a reviewer), so the same window gets a much tighter ceiling.
    report_rate_limit_max: int = 5

    # Posting is cheaper to abuse than voting but noisier than reporting: this is
    # what stops one account flooding a thread. Votes on comments ride the `vote`
    # bucket instead, since they cost the same as a review vote.
    comment_rate_limit_max: int = 10

    # --- Trust visibility thresholds (M2 slice 4; defaults OFF for cold start) ---
    product_trust_visibility_threshold: float = 0.0
    product_trust_min_reviews: int = 5

    # --- Fraud signals (M2 slice 5; advisory-only, never auto-block) ---
    duplicate_similarity_threshold: float = 0.85

    # --- Token economy (M2 slice 7) ---
    tokens_on_review_published: int = 10
    tokens_on_commission: int = 25

    # --- PII retention (M2 slice 8) — REQUIRED non-empty in production ---
    pii_hash_salt: str = "dev-pii-salt"

    # --- Request board (M3 slice 9) ---
    # Bounty and top-up settings lived here until migration 0022 retired the
    # request board's token economy. Posting is free and up-votes rank the
    # board rather than raising a purse, so there is nothing left to tune.
    request_ttl_days: int = 30            # open -> expired (escrow refunded)

    # --- Review contracts (M3 slice 10) ---
    contract_term_months: int = 6         # auto-renews unless the reviewer opts out

    # --- Payouts (M3 slice 11) ---
    payout_min_php: Decimal = Decimal("300.00")   # minimum wallet balance to schedule
    payout_provider: str = "paypal_sandbox"       # paypal_sandbox | paypal_live | manual
    paypal_client_id: str = ""
    paypal_secret: str = ""
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"

    # --- Lazada affiliate integration (M3 slice 12) ---
    # Postback: Lazada's macro set carries NO request signature, so the only thing
    # standing between the endpoint and forged conversions is this shared secret.
    # It must be long and random, and it is why postbacks never create money —
    # see app/services/postback_service.py.
    lazada_postback_secret: str = ""
    # Open API (signed) — the trustworthy source, used to reconcile into commissions.
    lazada_app_key: str = ""
    lazada_app_secret: str = ""
    lazada_user_token: str = ""
    lazada_api_base: str = "https://api.lazada.com.ph/rest"
    # Conversions older than this are not re-pulled on a routine sync.
    lazada_sync_lookback_days: int = 7

    @property
    def lazada_postback_enabled(self) -> bool:
        return bool(self.lazada_postback_secret)

    @property
    def lazada_api_enabled(self) -> bool:
        return bool(self.lazada_app_key and self.lazada_app_secret
                    and self.lazada_user_token)

    # --- Email + OTP (Slice 1 Phase A) ---
    email_provider: str = "console"      # console | resend
    resend_api_key: str = ""
    email_from: str = "onboarding@resend.dev"
    otp_ttl_seconds: int = 600
    otp_max_attempts: int = 5
    # Per-address send cap, enforced in Postgres. The Redis limiter fails open
    # (core/rate_limit.py), so without this a Redis outage turns
    # /auth/otp/request into an unmetered outbound-email pump.
    otp_send_window_seconds: int = 900
    otp_max_sends_per_window: int = 5

    # --- Proof-of-purchase access ---
    # TTL for a signed receipt URL. Short on purpose: the URL is a bearer
    # credential once issued, so its usefulness to anyone who intercepts it is
    # bounded by this number. Long enough for a moderator to open the image,
    # not long enough to be worth passing around.
    receipt_url_ttl_seconds: int = 300

    # --- CORS ---
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def affiliate_domains(self) -> dict[str, list[str]]:
        if self.affiliate_allowed_domains.strip():
            return json.loads(self.affiliate_allowed_domains)
        return DEFAULT_AFFILIATE_DOMAINS

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def effective_database_url(self) -> str:
        """The DB URL **migrations** use (Alembic).

        Session mode, deliberately: our migrations run `ALTER TYPE ... ADD VALUE`
        inside `autocommit_block()`, which needs a real session — the transaction
        pooler cannot provide one.

        When targeting Supabase, prefer the IPv4 session-pooler string (reachable
        from IPv4 networks) over the IPv6-only direct string.
        """
        if self.use_supabase:
            cs = (self.supabase_connection_string_session_pooler
                  or self.supabase_connection_string)
            if cs:
                return _to_sqlalchemy_pg_url(cs)
        return self.database_url

    @property
    def runtime_database_url(self) -> str:
        """The DB URL the **application** uses — Supabase TRANSACTION pooler.

        Measured on this project (2026-07-16): the session pooler accepts only
        **4** concurrent clients before
        `FATAL: (EMAXCONNSESSION) max clients reached in session mode`, while the
        transaction pooler accepted 30+. A 2-worker + Celery deployment needs far
        more than 4, so serving from the session pooler makes the API 500 under
        any real concurrency. Transaction mode multiplexes many clients onto few
        server connections — it is what an app tier is supposed to use.

        Derived from the session-pooler string by switching 5432 -> 6543 (same
        host; that is how Supabase exposes it) unless an explicit transaction
        string is configured. Prepared statements are disabled for it in
        `db_connect_args` — required for pgbouncer transaction mode.
        """
        if not self.use_supabase:
            return self.database_url
        if self.supabase_connection_string_transaction_pooler:
            return _to_sqlalchemy_pg_url(
                self.supabase_connection_string_transaction_pooler)
        session_cs = self.supabase_connection_string_session_pooler
        if session_cs:
            url = make_url(_to_sqlalchemy_pg_url(session_cs))
            if "pooler" in (url.host or "").lower():
                return url.set(port=6543).render_as_string(hide_password=False)
            return url.render_as_string(hide_password=False)
        return self.effective_database_url

    def _connect_args_for(self, database_url: str) -> dict:
        """psycopg connect kwargs for a given URL.

        - SSL required for Supabase hosts.
        - Prepared statements disabled for the poolers (pgbouncer), detected by
          host containing 'pooler' or port 6543.
        """
        url = make_url(database_url)
        host = (url.host or "").lower()
        args: dict = {}
        if "supabase" in host:
            args["sslmode"] = self.db_sslmode
        if "pooler" in host or url.port == 6543:
            args["prepare_threshold"] = None
        return args

    @property
    def db_connect_args(self) -> dict:
        """Connect kwargs for MIGRATIONS (session pooler)."""
        return self._connect_args_for(self.effective_database_url)

    @property
    def runtime_connect_args(self) -> dict:
        """Connect kwargs for the APPLICATION (transaction pooler)."""
        return self._connect_args_for(self.runtime_database_url)

    def production_issues(self) -> list[str]:
        """Hard requirements before serving production traffic."""
        issues: list[str] = []
        if self.jwt_secret in ("", "dev-insecure-change-me") or len(self.jwt_secret) < 32:
            issues.append("JWT_SECRET must be a strong random value (>= 32 chars).")
        if self.use_supabase and not (self.supabase_connection_string_session_pooler
                                       or self.supabase_connection_string):
            issues.append("USE_SUPABASE=true but no Supabase connection string is set.")
        if not self.use_supabase and "localhost" in self.database_url:
            issues.append("DATABASE_URL points at localhost; set USE_SUPABASE=true "
                          "or a managed DATABASE_URL in production.")
        if "*" in self.cors_origins:
            issues.append("CORS_ORIGINS must not contain '*' in production.")
        if "localhost" in self.cors_origins or "127.0.0.1" in self.cors_origins:
            issues.append("CORS_ORIGINS still points at localhost; a production "
                          "browser origin would be refused.")
        # Redis is the ONLY throttle on login/register brute force — the OTP caps
        # live in Postgres, but nothing else does. enforce_rate_limit fails open
        # (core/rate_limit.py), so an unreachable Redis removes that protection
        # silently rather than loudly.
        if "localhost" in self.redis_url or "127.0.0.1" in self.redis_url:
            issues.append("REDIS_URL still points at localhost; rate limiting "
                          "fails open, so auth brute-force protection would be "
                          "absent in production.")
        if self.pii_hash_salt in ("", "dev-pii-salt"):
            issues.append("PII_HASH_SALT must be a strong random value in production.")
        if self.payout_provider == "paypal_live" and not (
                self.paypal_client_id and self.paypal_secret):
            issues.append("PAYOUT_PROVIDER=paypal_live requires PAYPAL_CLIENT_ID "
                          "and PAYPAL_SECRET.")
        # The postback URL is public and Lazada signs nothing, so a short or absent
        # secret means anyone who guesses the path can fabricate conversion rows.
        if self.lazada_postback_secret and len(self.lazada_postback_secret) < 32:
            issues.append("LAZADA_POSTBACK_SECRET must be >= 32 chars; it is the only "
                          "thing authenticating a public, unsigned postback endpoint.")
        if self.payout_provider == "paypal_live" and "sandbox" in self.paypal_base_url:
            issues.append("PAYOUT_PROVIDER=paypal_live but PAYPAL_BASE_URL still "
                          "points at the sandbox.")
        # The console provider only logs codes — in production that means every
        # OTP silently fails to reach the user, and the codes land in the logs.
        if self.email_provider == "console":
            issues.append("EMAIL_PROVIDER=console only logs OTP codes; set a real "
                          "provider (resend) before serving production traffic.")
        if self.email_provider == "resend" and not self.resend_api_key:
            issues.append("EMAIL_PROVIDER=resend requires RESEND_API_KEY.")
        # NOT a blocking issue, by owner decision: the shared resend.dev sender
        # is accepted for now. Be aware of what it costs — Resend answers 403 for
        # any recipient other than the account owner, so sign-up works only for
        # that address until a domain is verified. Deliverability also suffers:
        # a shared sender has no SPF/DKIM alignment with bluntly.ph.
        # Serving from the session pooler is a hard fail in production: it caps
        # at ~4 concurrent clients, so the API 500s under any real load.
        if self.use_supabase:
            runtime = make_url(self.runtime_database_url)
            if "pooler" in (runtime.host or "").lower() and runtime.port != 6543:
                issues.append(
                    "The app is pointed at the Supabase SESSION pooler "
                    f"(:{runtime.port}), which allows only ~4 concurrent clients "
                    "and will 500 under load. Use the TRANSACTION pooler (:6543) "
                    "— set SUPABASE_CONNECTION_STRING_TRANSACTION_POOLER.")
        pool_capacity = self.db_pool_size + self.db_max_overflow
        if self.threadpool_tokens > pool_capacity:
            issues.append(
                f"THREADPOOL_TOKENS ({self.threadpool_tokens}) exceeds the DB pool "
                f"capacity ({pool_capacity} = DB_POOL_SIZE + DB_MAX_OVERFLOW). Sync "
                "endpoints hold a connection for their whole life, so the surplus "
                "would queue on the pool and 500 after DB_POOL_TIMEOUT under load.")
        return issues


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
