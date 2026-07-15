"""Application settings, loaded from environment / repo-root .env.

Single source of truth for configuration. All secrets come from the environment;
nothing is hardcoded (see PRD §8 / Architecture §7 security notes).
"""

from __future__ import annotations

import json
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
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout: int = 10       # fail fast instead of 30s pile-ups
    db_pool_recycle: int = 300      # safe for the Supabase session pooler
    threadpool_tokens: int = 40     # AnyIO threadpool ceiling for sync endpoints

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
    supabase_connection_string_session_pooler: str = ""

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

    # --- Trust visibility thresholds (M2 slice 4; defaults OFF for cold start) ---
    product_trust_visibility_threshold: float = 0.0
    product_trust_min_reviews: int = 5
    seller_trust_visibility_threshold: float = 0.0

    # --- Fraud signals (M2 slice 5; advisory-only, never auto-block) ---
    duplicate_similarity_threshold: float = 0.85

    # --- Token economy (M2 slice 7) ---
    tokens_on_review_published: int = 10
    tokens_on_commission: int = 25

    # --- PII retention (M2 slice 8) — REQUIRED non-empty in production ---
    pii_hash_salt: str = "dev-pii-salt"

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
        """The DB URL the app/migrations actually use.

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
    def db_connect_args(self) -> dict:
        """psycopg connect kwargs derived from the effective URL.

        - SSL required for Supabase hosts.
        - Prepared statements disabled for the transaction pooler (pgbouncer),
          detected by host containing 'pooler' or port 6543.
        """
        url = make_url(self.effective_database_url)
        host = (url.host or "").lower()
        args: dict = {}
        if "supabase.co" in host or "supabase.com" in host:
            args["sslmode"] = self.db_sslmode
        if "pooler" in host or url.port == 6543:
            args["prepare_threshold"] = None
        return args

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
        if self.pii_hash_salt in ("", "dev-pii-salt"):
            issues.append("PII_HASH_SALT must be a strong random value in production.")
        return issues


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
