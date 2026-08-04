"""Lazada Open API client — signed, and therefore trustworthy.

This is the counterpart to `postback_service`. A postback arrives unsigned over a
URL anyone might see, so it cannot authorise money. A call *here* is signed with
the app secret and answered by Lazada directly, which is what makes
`/marketing/conversion/report` an acceptable source for creating commissions.

Signing follows the Alibaba/Lazada TOP scheme:

    sign = HMAC_SHA256(app_secret,
                       api_path + concat(sorted(k + v for non-empty params)))
           .hexdigest().upper()

`sign` itself is excluded, byte-sorted by key, and the API path is prefixed —
omitting the path is the usual cause of a silent IncompleteSignature.

Read-only. Nothing here mutates Lazada state.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("lazada")

CONVERSION_REPORT_PATH = "/marketing/conversion/report"
GETLINK_PATH = "/marketing/getlink"

# Their docs cap batch getlink at 100 inputs and share a 400 QPS ceiling across
# all six country sites, with throttling as the stated penalty for abuse.
MAX_GETLINK_INPUTS = 100
DEFAULT_PAGE_SIZE = 100


class LazadaError(RuntimeError):
    """A Lazada API call failed or returned an error envelope."""


def sign(api_path: str, params: dict[str, Any], app_secret: str) -> str:
    """TOP signature over the api path + sorted non-empty params."""
    parts = [api_path]
    for key in sorted(params):
        value = params[key]
        if value is None or value == "":
            continue
        parts.append(f"{key}{value}")
    payload = "".join(parts).encode("utf-8")
    return hmac.new(app_secret.encode("utf-8"), payload,
                    hashlib.sha256).hexdigest().upper()


def _signed_params(api_path: str, extra: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {
        "app_key": settings.lazada_app_key,
        "timestamp": str(int(time.time() * 1000)),  # ms since epoch, per their SDK
        "sign_method": "sha256",
        **{k: v for k, v in extra.items() if v is not None and v != ""},
    }
    params["sign"] = sign(api_path, params, settings.lazada_app_secret)
    return params


def _call(api_path: str, extra: dict[str, Any], *, timeout: float = 30.0) -> dict:
    if not settings.lazada_api_enabled:
        raise LazadaError("Lazada API credentials are not configured "
                          "(LAZADA_APP_KEY / LAZADA_APP_SECRET / LAZADA_USER_TOKEN).")
    url = settings.lazada_api_base.rstrip("/") + api_path
    params = _signed_params(api_path, extra)
    try:
        response = httpx.get(url, params=params, timeout=timeout)
    except httpx.HTTPError as exc:
        raise LazadaError(f"Lazada request failed: {exc}") from exc
    if response.status_code >= 400:
        raise LazadaError(f"Lazada HTTP {response.status_code}: {response.text[:300]}")
    body = response.json()
    # Their envelope reports failure in-band with a 200.
    code = str(body.get("code", "0"))
    if code not in ("0", "", "None"):
        raise LazadaError(f"Lazada error {code}: {body.get('message') or body}")
    return body


@dataclass(frozen=True)
class Conversion:
    """One sub-order row from /marketing/conversion/report.

    `est_payout` is Lazada's word, not ours — it moves as an order goes
    fulfilled -> delivered -> returned, which is precisely why a conversion is
    not payable the moment it appears.
    """

    order_id: str
    sub_order_id: str
    status: str | None
    est_payout: str | None
    order_amount: str | None
    currency: str | None
    conversion_time: str | None
    sub_id1: str | None
    sub_id2: str | None
    validity: str | None
    raw: dict

    @property
    def is_returned(self) -> bool:
        return (self.status or "").strip().lower() in {"returned", "cancelled", "canceled"}


def _as_conversion(row: dict) -> Conversion:
    return Conversion(
        order_id=str(row.get("orderId") or ""),
        sub_order_id=str(row.get("subOrderId") or ""),
        status=row.get("status"),
        est_payout=row.get("estPayout"),
        order_amount=row.get("orderAmt"),
        currency=row.get("currency"),
        conversion_time=row.get("conversionTime"),
        sub_id1=row.get("subId1"),
        sub_id2=row.get("subId2"),
        validity=row.get("validity"),
        raw=row,
    )


def _rows(body: dict) -> list[dict]:
    """Dig the row list out of whichever envelope shape came back."""
    data = body.get("data") or body.get("result") or {}
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    for key in ("data", "list", "records", "conversions", "result"):
        candidate = data.get(key) if isinstance(data, dict) else None
        if isinstance(candidate, list):
            return [r for r in candidate if isinstance(r, dict)]
    return []


def fetch_conversions(date_start: date, date_end: date, *,
                      page_size: int = DEFAULT_PAGE_SIZE,
                      max_pages: int = 50) -> list[Conversion]:
    """Every conversion in [date_start, date_end], following pagination.

    `max_pages` is a guard, not a limit to tune: without it a malformed envelope
    that never reports exhaustion would loop against a rate-limited API.
    """
    out: list[Conversion] = []
    for page in range(1, max_pages + 1):
        body = _call(CONVERSION_REPORT_PATH, {
            "userToken": settings.lazada_user_token,
            "dateStart": date_start.isoformat(),
            "dateEnd": date_end.isoformat(),
            "limit": page_size,
            "page": page,
        })
        rows = _rows(body)
        out.extend(_as_conversion(r) for r in rows)
        if len(rows) < page_size:
            break
    else:
        log.warning("conversion report hit the page guard; results may be truncated",
                    extra={"extra_fields": {"max_pages": max_pages}})
    log.info("fetched lazada conversions", extra={"extra_fields": {
        "count": len(out), "from": date_start.isoformat(), "to": date_end.isoformat()}})
    return out


def get_tracking_links(product_urls: list[str], *, sub_id1: str | None = None,
                       sub_id2: str | None = None) -> dict[str, str]:
    """Map {product url -> tracking link} via batch getlink.

    Lets a moderator monetise a Lazada review without leaving the queue: paste
    the product URL, get the affiliate link back already carrying our sub-IDs.
    Shopee has no equivalent, so that flow stays manual.
    """
    if not product_urls:
        return {}
    if len(product_urls) > MAX_GETLINK_INPUTS:
        raise LazadaError(f"batch getlink accepts at most {MAX_GETLINK_INPUTS} URLs.")
    body = _call(GETLINK_PATH, {
        "userToken": settings.lazada_user_token,
        "inputType": "url",
        "inputValue": ",".join(product_urls),
        "subId1": sub_id1,
        "subId2": sub_id2,
    })
    data = body.get("data") or {}
    rows = data.get("urlBatchGetLinkInfoList") or []
    links: dict[str, str] = {}
    for row in rows:
        original = row.get("originalUrl")
        link = row.get("regularPromotionLink") or row.get("mmPromotionLink")
        if original and link:
            links[original] = link
    errors = data.get("errorInfoList") or []
    if errors:
        log.warning("batch getlink returned errors", extra={"extra_fields": {
            "count": len(errors), "first": str(errors[0])[:200]}})
    return links
