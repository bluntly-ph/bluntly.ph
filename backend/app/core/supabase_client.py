"""Supabase server-side clients.

Two clients, matching §7.1 of the build prompt:
  * publishable (anon) client — RLS-constrained, safe for user-scoped reads.
  * service-role client — bypasses RLS for privileged jobs (admin CSV import,
    Honesty Fund distribution, PII retention). SERVER-ONLY; never sent to client.

These are what make SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY / SUPABASE_SECRET_KEY
live configuration rather than dead placeholders (§7.1). Storage usage arrives
in M1 (proof photos/receipts); the clients are defined here in M0.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


@lru_cache
def get_anon_client() -> Client:
    """RLS-constrained client (publishable key)."""
    if not (settings.supabase_url and settings.supabase_publishable_key):
        raise RuntimeError("Supabase publishable credentials are not configured.")
    return create_client(settings.supabase_url, settings.supabase_publishable_key)


@lru_cache
def get_service_client() -> Client:
    """RLS-bypassing client (secret/service-role key). Server-only."""
    if not (settings.supabase_url and settings.supabase_secret_key):
        raise RuntimeError("Supabase service-role credentials are not configured.")
    return create_client(settings.supabase_url, settings.supabase_secret_key)
