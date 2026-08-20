"""Email delivery adapter (Slice 1 Phase A).

Mirrors the shape of `adapters/paypal.py`: the adapter never touches the
database and never decides policy — it sends and reports.

Two providers:
  * `console` — logs the code. The local and TEST default; makes OTP fully
    developable and testable with no vendor key and no network.
  * `resend`  — POST https://api.resend.com/emails with a Bearer key.

Missing or unknown credentials raise `EmailNotConfigured` rather than silently
no-oping, so a misconfigured box fails loudly instead of swallowing codes.

The plaintext code must never appear on a failure path — an exception message
carrying it would leak into logs and error trackers.
"""

from __future__ import annotations

import httpx

from app.adapters.email_templates import otp_html, otp_subject, otp_text
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("adapters.email")

RESEND_URL = "https://api.resend.com/emails"
_TIMEOUT = httpx.Timeout(10.0)


class EmailNotConfigured(RuntimeError):
    """Provider missing or unknown — the caller should surface a 500, not a 2xx."""


class EmailSendError(RuntimeError):
    """The provider rejected the request or was unreachable."""


def _ttl_minutes() -> int:
    return max(settings.otp_ttl_seconds // 60, 1)


def send_otp_email(to: str, code: str) -> None:
    """Deliver a one-time code. Raises on misconfiguration or provider failure."""
    provider = settings.email_provider
    if provider == "console":
        # Deliberately logs the code: this provider exists so developers and the
        # test suite can complete an OTP round trip offline.
        log.info("OTP email (console provider)",
                 extra={"extra_fields": {"to": to, "code": code}})
        return
    if provider != "resend":
        raise EmailNotConfigured(f"Unknown EMAIL_PROVIDER {provider!r}.")
    if not settings.resend_api_key:
        raise EmailNotConfigured("EMAIL_PROVIDER=resend but RESEND_API_KEY is empty.")

    try:
        response = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                # A display name is what turns "onboarding@resend.dev" into
                # "bluntly" in the inbox list — worth doing regardless of which
                # address is actually sending.
                "from": f"bluntly <{settings.email_from}>",
                "to": [to],
                "subject": otp_subject(code),
                # Both parts: text is a real deliverability signal and some
                # recipients read text only.
                "html": otp_html(code, _ttl_minutes()),
                "text": otp_text(code, _ttl_minutes()),
            },
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise EmailSendError(f"Resend unreachable: {exc}") from exc
    if response.status_code >= 400:
        # Never include the code here - this string reaches logs and trackers.
        #
        # And never the provider's body either. It echoes the recipient address
        # back, and otp_service logs this message alongside the address it
        # already records, so the body duplicated PII into the log for every
        # failed send. The status is what an operator can act on; the body is
        # in the provider's own dashboard.
        raise EmailSendError(f"Resend rejected the send (HTTP {response.status_code})")
