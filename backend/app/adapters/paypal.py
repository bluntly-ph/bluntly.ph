"""PayPal Payouts API adapter (M3 slice 11).

Built to the documented v1 contract
(https://developer.paypal.com/docs/api/payments.payouts-batch/v1/):

  auth   POST /v1/oauth2/token          Basic(client_id:secret), grant_type=client_credentials
  submit POST /v1/payments/payouts      {sender_batch_header{sender_batch_id,...}, items[]}
         -> {batch_header:{payout_batch_id, batch_status}}
  poll   GET  /v1/payments/payouts/{id} -> batch_status + items[].transaction_status

Two contract details we lean on deliberately:
  * PayPal **rejects a duplicate `sender_batch_id` used within the last 30 days**
    — a second submission of the same cycle can't double-pay.
  * `PayPal-Request-Id` gives request-level idempotency on retries.

The adapter never touches the database and never decides policy: it submits and
reports. Missing credentials raise `PayPalNotConfigured` so the caller can leave
the batch `scheduled` (manual mode stays available) instead of crashing.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("adapters.paypal")

# batch_status (POST + GET) per the API reference.
BATCH_PENDING = "PENDING"
BATCH_PROCESSING = "PROCESSING"
BATCH_SUCCESS = "SUCCESS"
BATCH_DENIED = "DENIED"
BATCH_CANCELED = "CANCELED"
TERMINAL_FAILURE_BATCH = {BATCH_DENIED, BATCH_CANCELED}

# items[].transaction_status per the API reference.
TXN_SUCCESS = "SUCCESS"
TXN_FAILED = "FAILED"
TXN_PENDING = "PENDING"
TXN_UNCLAIMED = "UNCLAIMED"
TXN_RETURNED = "RETURNED"
TXN_ONHOLD = "ONHOLD"
TXN_BLOCKED = "BLOCKED"
TXN_REFUNDED = "REFUNDED"
TXN_REVERSED = "REVERSED"
# Money did not (or no longer will) reach the recipient -> refund the wallet.
TXN_FAILURES = {TXN_FAILED, TXN_RETURNED, TXN_BLOCKED, TXN_REFUNDED, TXN_REVERSED}


class PayPalNotConfigured(RuntimeError):
    """Credentials absent — caller should leave the batch scheduled and log."""


class PayPalError(RuntimeError):
    """PayPal rejected the request or was unreachable."""


@dataclass(frozen=True)
class PayoutItem:
    receiver: str          # payout_account (an email; recipient_type EMAIL)
    amount: Decimal
    sender_item_id: str    # our payout_id
    currency: str = "PHP"
    note: str = "Bluntly.ph earnings payout"


@dataclass(frozen=True)
class BatchResult:
    payout_batch_id: str
    batch_status: str


def is_configured() -> bool:
    return bool(settings.paypal_client_id and settings.paypal_secret)


def _token(client: httpx.Client) -> str:
    resp = client.post(
        "/v1/oauth2/token",
        auth=(settings.paypal_client_id, settings.paypal_secret),
        data={"grant_type": "client_credentials"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code != 200:
        raise PayPalError(f"OAuth failed: HTTP {resp.status_code}")
    return resp.json()["access_token"]


def submit_batch(sender_batch_id: str, items: list[PayoutItem]) -> BatchResult:
    """POST /v1/payments/payouts. Raises PayPalNotConfigured / PayPalError."""
    if not is_configured():
        raise PayPalNotConfigured("PAYPAL_CLIENT_ID / PAYPAL_SECRET are not set.")
    body = {
        "sender_batch_header": {
            "sender_batch_id": sender_batch_id,
            "email_subject": "You have a payout from Bluntly.ph",
            "email_message": "Your Bluntly.ph earnings have been sent.",
        },
        "items": [
            {
                "recipient_type": "EMAIL",
                "amount": {"value": f"{i.amount:.2f}", "currency": i.currency},
                "receiver": i.receiver,
                "note": i.note,
                "sender_item_id": i.sender_item_id,
            }
            for i in items
        ],
    }
    with httpx.Client(base_url=settings.paypal_base_url, timeout=30.0) as client:
        token = _token(client)
        resp = client.post(
            "/v1/payments/payouts", json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                # Request-level idempotency for safe retries.
                "PayPal-Request-Id": f"{sender_batch_id}-{uuid.uuid4().hex[:8]}",
            },
        )
    if resp.status_code not in (200, 201, 202):
        log.info("paypal payout submit rejected",
                 extra={"extra_fields": {"status": resp.status_code,
                                         "batch": sender_batch_id}})
        raise PayPalError(f"Payout submit failed: HTTP {resp.status_code}")
    header = resp.json().get("batch_header") or {}
    return BatchResult(payout_batch_id=header.get("payout_batch_id", ""),
                       batch_status=header.get("batch_status", BATCH_PENDING))


def get_batch(payout_batch_id: str) -> dict:
    """GET /v1/payments/payouts/{id} -> {batch_status, items: {sender_item_id: status}}."""
    if not is_configured():
        raise PayPalNotConfigured("PAYPAL_CLIENT_ID / PAYPAL_SECRET are not set.")
    with httpx.Client(base_url=settings.paypal_base_url, timeout=30.0) as client:
        token = _token(client)
        resp = client.get(f"/v1/payments/payouts/{payout_batch_id}",
                          headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        raise PayPalError(f"Payout status fetch failed: HTTP {resp.status_code}")
    data = resp.json()
    items = {}
    for item in data.get("items") or []:
        sid = (item.get("payout_item") or {}).get("sender_item_id")
        if sid:
            items[sid] = item.get("transaction_status")
    return {"batch_status": (data.get("batch_header") or {}).get("batch_status"),
            "items": items}
