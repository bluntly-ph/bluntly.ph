"""One rule for every user-supplied URL the interface later renders as a link.

`javascript:`, `data:` and `vbscript:` URLs are script execution the moment
somebody clicks them, in whichever session does the clicking - and for most of
these fields that session belongs to a moderator, reviewing content chosen by
the person who submitted it.

This began as a validator on `ReportCreate.evidence_url`, with the reasoning
written out in full. The reasoning was right and the placement was wrong: it
guarded one field while `products.source_url` and `review_requests.source_url`
carried the same kind of string to the same moderator queue with nothing but a
length cap. `ModerationQueue.tsx` renders the product one as `href` directly.

So it lives here, and fields opt in by name rather than by anybody remembering.
"""

from __future__ import annotations

# http(s) only. An allowlist, because the interesting schemes are the ones
# nobody thinks of - `vbscript:`, `blob:`, `filesystem:` - and a blocklist
# would have to predict them.
ALLOWED_URL_SCHEMES = ("http://", "https://")


def web_url_or_none(value: str | None, *, field: str = "Links") -> str | None:
    """Normalise to a web URL, None, or raise.

    Blank means "not provided", which is different from "provided and bad" -
    the first is a legitimate state for every field using this, and the second
    is the one worth refusing.
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not value.lower().startswith(ALLOWED_URL_SCHEMES):
        raise ValueError(f"{field} must start with http:// or https://.")
    return value
