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
from datetime import date, timedelta
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
        # The body is not included: the signed request carries app_key and a
        # signature, and an error response can echo request context back. The
        # status is what an operator acts on; the body is in Lazada's console.
        raise LazadaError(f"Lazada HTTP {response.status_code}")
    # A 200 carrying a non-JSON body is a provider fault, and it has to arrive
    # as LazadaError like every other failure here - callers catch that, not
    # JSONDecodeError. Same class of bug as the PayPal OAuth parse.
    try:
        body = response.json()
    except Exception as exc:  # noqa: BLE001
        raise LazadaError("Lazada returned a non-JSON response") from exc
    # Their envelope reports failure in-band with a 200.
    code = str(body.get("code", "0"))
    if code not in ("0", "", "None"):
        # `or body` would fall back to dumping the whole payload whenever the
        # provider omits a message - which is exactly the case where the body
        # is least predictable. Code plus message, or code alone.
        message = body.get("message")
        raise LazadaError(f"Lazada error {code}: {message}" if message
                          else f"Lazada error {code}")
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


#: Buyer identity the conversion API returns and this application must never
#: hold. Scrubbed at the boundary rather than at each write, because `raw` is
#: persisted verbatim into `affiliate_postbacks.raw` — so anything that reaches
#: a Conversion object is one ordinary code path away from the database.
#: Matching is case-insensitive and by substring: Lazada has shipped both
#: `memberEmail` and `member_email` in different envelope versions.
_PII_FIELD_MARKERS = (
    "memberemail", "membername", "memberid", "member_email", "member_name",
    "member_id", "buyeremail", "buyername", "buyerid", "buyer_email",
    "buyer_name", "buyer_id", "email", "phone", "mobile",
)


def scrub_buyer_identity(row: dict) -> dict:
    """A provider row with buyer identity removed.

    The affiliate ledger needs to know that a sale happened and what it earned;
    it never needs to know who bought. Removing the fields here means no
    downstream caller has to remember to, and the removal is verifiable in one
    place.
    """
    return {
        key: value for key, value in row.items()
        if not any(marker in str(key).lower().replace(" ", "")
                   for marker in _PII_FIELD_MARKERS)
    }


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
        raw=scrub_buyer_identity(row),
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


def month_windows(date_start: date, date_end: date) -> list[tuple[date, date]]:
    """Split an inclusive range into per-calendar-month windows.

    Lazada refuses a multi-month request outright — the API answers
    "only support fetch single month data" — so asking for a quarter returns an
    error rather than three months of rows. Callers should not have to know
    that, so the range is split here and the results merged.

    Windows are clipped to the caller's own bounds, so a range starting on the
    17th begins on the 17th rather than the 1st.
    """
    if date_end < date_start:
        return []

    windows: list[tuple[date, date]] = []
    cursor = date_start
    while cursor <= date_end:
        # First day of the following month, without dateutil.
        if cursor.month == 12:
            next_month = date(cursor.year + 1, 1, 1)
        else:
            next_month = date(cursor.year, cursor.month + 1, 1)
        window_end = min(next_month - timedelta(days=1), date_end)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return windows


def _fetch_one_month(date_start: date, date_end: date, *, page_size: int,
                     max_pages: int) -> list[Conversion]:
    """One single-month window, following pagination.

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
    return out


def fetch_conversions(date_start: date, date_end: date, *,
                      page_size: int = DEFAULT_PAGE_SIZE,
                      max_pages: int = 50) -> list[Conversion]:
    """Every conversion in [date_start, date_end], across as many months as it spans.

    Deduplicated on `subOrderId`, which the owner's real export proves is unique
    on its own (218 distinct values in 218 rows). Windows are clipped so they
    never overlap, but a row whose status changes between two calls would
    otherwise appear twice; the LAST sighting wins, because it is the more
    recent word from the provider about the same sub-order.
    """
    seen: dict[str, Conversion] = {}
    windows = month_windows(date_start, date_end)
    for window_start, window_end in windows:
        for conversion in _fetch_one_month(window_start, window_end,
                                           page_size=page_size,
                                           max_pages=max_pages):
            # A row with no sub-order id cannot be deduplicated, and dropping it
            # would silently lose a sale; key it by identity instead.
            key = conversion.sub_order_id or f"_row{id(conversion)}"
            seen[key] = conversion

    out = list(seen.values())
    log.info("fetched lazada conversions", extra={"extra_fields": {
        "count": len(out), "windows": len(windows),
        "from": date_start.isoformat(), "to": date_end.isoformat()}})
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
