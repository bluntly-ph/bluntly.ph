"""Supabase Storage helpers (Slice 1 Phase A).

This is the first real Storage integration — supabase_client.py has carried the
clients since M0 with no consumer. Kept generic so review proof photos can reuse
`validate_image` / the upload shape later.

Content type is sniffed from magic bytes and never trusted from the request: a
browser-supplied Content-Type is attacker-controlled, and storing an
`image/png`-labelled HTML file in a public bucket is a stored-XSS vector.
"""

from __future__ import annotations

import uuid

from app.core.errors import AppError
from app.core.supabase_client import get_service_client

AVATAR_BUCKET = "avatars"
# Measured against production 2026-08-20: the platform refuses a request body
# somewhere between 3.0 MB and 4.4 MB with a bare 413, before any of this code
# runs. A cap above that is a cap the API can never enforce - the user gets a
# platform error page instead of a sentence explaining what went wrong. 4 MB
# leaves room for multipart overhead underneath it.
#
# Product images are not in this list on purpose: they are uploaded by
# scripts/seed_product_images.py straight to Supabase Storage, so they never
# cross a serverless function and the platform limit does not apply.
UPLOAD_CEILING_BYTES = 4 * 1024 * 1024

#: How long a public image may be cached, in SECONDS-AS-A-STRING.
#:
#: The unit matters: storage3 emits ``Cache-Control: max-age={this}``, so a full
#: directive here would render as ``max-age=public, max-age=...``. Seconds only.
#:
#: This has to be passed explicitly on every public upload. storage3 carries a
#: sane default (``DEFAULT_FILE_OPTIONS``, cache-control 3600) but applies it
#: only when ``file_options`` is omitted entirely - passing a partial dict, as
#: every call here does, silently discards it and Supabase then serves the
#: object ``Cache-Control: no-cache``. Measured on production 2026-08-23: the
#: product image on /search was refetched in full (120,455 B, CF-Cache-Status
#: MISS) on every single page load, and was the page's LCP element at 9.25 s
#: under Lighthouse's throttling. /feed scored better only because its LCP
#: happens to be a text node rather than an image.
#:
#: A year is safe because every object path ends in a fresh uuid4 hex, so a
#: given path's bytes never change; a replacement image is written to a new
#: path and referenced by a new URL.
PUBLIC_IMAGE_MAX_AGE = "31536000"

MAX_AVATAR_BYTES = UPLOAD_CEILING_BYTES

# (magic prefix, mime, file extension)
_MAGIC: tuple[tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"RIFF", "image/webp", "webp"),   # RIFF....WEBP
)


def sniff_image_type(data: bytes) -> str | None:
    """Return the MIME type implied by the leading bytes, or None."""
    for magic, mime, _ in _MAGIC:
        if not data.startswith(magic):
            continue
        # RIFF is a container: only the WEBP form is an image.
        if mime == "image/webp" and data[8:12] != b"WEBP":
            continue
        return mime
    return None


def _extension_for(mime: str) -> str:
    for _, candidate, ext in _MAGIC:
        if candidate == mime:
            return ext
    raise AppError("Unsupported image type.", code="unsupported_media_type",
                   status_code=415, title="Unsupported media type")


def validate_avatar(data: bytes) -> str:
    """Return the sniffed MIME type, or raise an AppError."""
    if len(data) > MAX_AVATAR_BYTES:
        raise AppError("Avatar must be 5 MB or smaller.", code="file_too_large",
                       status_code=413, title="File too large")
    mime = sniff_image_type(data)
    if mime is None:
        raise AppError("Avatar must be a PNG, JPEG, or WebP image.",
                       code="unsupported_media_type", status_code=415,
                       title="Unsupported media type")
    return mime


def upload_avatar(user_id: uuid.UUID, data: bytes) -> str:
    """Store the object and return its public URL."""
    mime = validate_avatar(data)
    path = f"{user_id}/{uuid.uuid4().hex}.{_extension_for(mime)}"
    bucket = get_service_client().storage.from_(AVATAR_BUCKET)
    bucket.upload(path, data, {"content-type": mime, "upsert": "false",
                           "cache-control": PUBLIC_IMAGE_MAX_AGE})
    return bucket.get_public_url(path)


def review_photo_belongs_to(url: str, user_id: uuid.UUID) -> bool:
    """True only if `url` is a review photo THIS user uploaded through us.

    FR-3 makes the product photograph the thing that turns a review
    "verified", and FR-8 layer 1 states the deterrent plainly: faking a review
    should cost at least what the product costs. Both collapse if the field is
    just a string - `photo_url: "https://anything"` self-certifies a review as
    verified, which also unlocks earning eligibility under FR-6.

    So the value has to be one of our own objects, in the public review bucket,
    under the submitting user's prefix. `upload_review_photo` writes exactly
    `.../<REVIEW_BUCKET>/<user_id>/<uuid>.<ext>`, so the check is the same
    shape as `receipt_key_belongs_to`.
    """
    if not url:
        return False
    marker = f"/{REVIEW_BUCKET}/"
    if marker not in url:
        return False
    path = url.split(marker, 1)[1].split("?", 1)[0]
    return path.split("/", 1)[0] == str(user_id) if "/" in path else False


def delete_avatar_object(url: str) -> None:
    """Best-effort removal of a previously uploaded object.

    A stale object is wasted bytes, not a correctness problem — never fail the
    caller's request over it.
    """
    marker = f"/{AVATAR_BUCKET}/"
    if marker not in url:
        return
    path = url.split(marker, 1)[1].split("?", 1)[0]
    try:
        get_service_client().storage.from_(AVATAR_BUCKET).remove([path])
    except Exception:  # noqa: BLE001
        pass


PRODUCT_BUCKET = "product-images"
MAX_PRODUCT_IMAGE_BYTES = 5 * 1024 * 1024


def validate_product_image(data: bytes) -> str:
    """Return the sniffed MIME type, or raise an AppError.

    Same magic-byte discipline as avatars: a merchant server's Content-Type is
    no more trustworthy than a browser's.
    """
    if len(data) > MAX_PRODUCT_IMAGE_BYTES:
        raise AppError("Product image must be 5 MB or smaller.", code="file_too_large",
                       status_code=413, title="File too large")
    mime = sniff_image_type(data)
    if mime is None:
        raise AppError("Product image must be a PNG, JPEG, or WebP image.",
                       code="unsupported_media_type", status_code=415,
                       title="Unsupported media type")
    return mime


def upload_product_image(product_id: uuid.UUID, data: bytes) -> str:
    """Upload to the public product-images bucket and return the public URL."""
    mime = validate_product_image(data)
    path = f"{product_id}/{uuid.uuid4().hex}.{_extension_for(mime)}"
    client = get_service_client()
    client.storage.from_(PRODUCT_BUCKET).upload(
        path, data, {"content-type": mime, "upsert": "true",
                     "cache-control": PUBLIC_IMAGE_MAX_AGE})
    return client.storage.from_(PRODUCT_BUCKET).get_public_url(path)


REVIEW_BUCKET = "review-photos"
MAX_REVIEW_PHOTO_BYTES = UPLOAD_CEILING_BYTES


def validate_review_photo(data: bytes) -> str:
    """Return the sniffed MIME type, or raise an AppError (BUG-023).

    The allowance is larger than an avatar's because a product photographed on
    a modern phone routinely clears 5 MB, and rejecting a valid proof photo is
    worse than storing a few extra megabytes. Same magic-byte discipline as
    everywhere else in this module - the browser's Content-Type is
    attacker-controlled.

    This is the PUBLIC half of review media (PRD FR-3: the product photograph
    shown on the published review). Proof of purchase is a different class of
    object entirely and lives in the private receipt bucket below.

    Note HEIC is deliberately absent. iOS Safari transcodes to JPEG on upload,
    and accepting a format nothing in the pipeline can render would trade a
    clear rejection at the door for a broken image on the published review.
    """
    if len(data) > MAX_REVIEW_PHOTO_BYTES:
        raise AppError("Photo must be 8 MB or smaller.", code="file_too_large",
                       status_code=413, title="File too large")
    mime = sniff_image_type(data)
    if mime is None:
        raise AppError("Photo must be a PNG, JPEG, or WebP image.",
                       code="unsupported_media_type", status_code=415,
                       title="Unsupported media type")
    return mime


def upload_review_photo(user_id: uuid.UUID, data: bytes) -> str:
    """Store a public review photo and return its public URL.

    Keyed by uploader rather than by review: the photo is chosen while the
    review is still being written and has no id yet.

    Public is correct here and only here - this image is review content, drawn
    on the published page for anyone to see. Never route a receipt through this
    function; see `upload_receipt`.
    """
    mime = validate_review_photo(data)
    path = f"{user_id}/{uuid.uuid4().hex}.{_extension_for(mime)}"
    client = get_service_client()
    client.storage.from_(REVIEW_BUCKET).upload(
        path, data, {"content-type": mime, "upsert": "false",
                     "cache-control": PUBLIC_IMAGE_MAX_AGE})
    return client.storage.from_(REVIEW_BUCKET).get_public_url(path)


# --------------------------------------------------------------------------
# Proof of purchase (private)
#
# A receipt is not review media. It routinely carries the buyer's name,
# delivery address, order number and prices, and the PRD scopes it to
# moderator evaluation of the earn_eligible gate (FR-3, FR-9) - not to
# readers. It therefore lives in its own PRIVATE bucket and is addressed by an
# opaque object key rather than a URL.
#
# The distinction is the whole point: a public URL moves the authorization
# decision out of the application and into a string. A string cannot be
# revoked, never expires, and leaks through browser history, Referer headers,
# proxy logs and screenshots. Authorization has to be a decision made per
# request against the caller's identity, which is what `signed_receipt_url`
# below exists to allow the API to do.
# --------------------------------------------------------------------------

RECEIPT_BUCKET = "review-receipts"
MAX_RECEIPT_BYTES = UPLOAD_CEILING_BYTES


def validate_receipt(data: bytes) -> str:
    """Return the sniffed MIME type, or raise an AppError.

    Identical discipline to every other upload in this module - the browser's
    Content-Type is attacker-controlled, so the magic bytes decide. Being a
    private bucket is not a reason to relax it: a mislabelled object is still
    served to a moderator later.
    """
    if len(data) > MAX_RECEIPT_BYTES:
        raise AppError("Proof of purchase must be 8 MB or smaller.",
                       code="file_too_large", status_code=413,
                       title="File too large")
    mime = sniff_image_type(data)
    if mime is None:
        raise AppError("Proof of purchase must be a PNG, JPEG, or WebP image.",
                       code="unsupported_media_type", status_code=415,
                       title="Unsupported media type")
    return mime


def upload_receipt(user_id: uuid.UUID, data: bytes) -> str:
    """Store a receipt privately and return its OBJECT KEY - never a URL.

    Keyed by uploader because the receipt is attached while the review is still
    a draft and has no id yet. The prefix is also load-bearing for
    authorization: `receipt_key_belongs_to` reads it to reject a caller who
    submits someone else's key with their own review.
    """
    mime = validate_receipt(data)
    key = f"{user_id}/{uuid.uuid4().hex}.{_extension_for(mime)}"
    # No cache-control on purpose. A receipt is private evidence reached
    # through a short-lived signed URL; a year of shared caching is the wrong
    # lifetime for it, and the default no-cache is the right one here.
    get_service_client().storage.from_(RECEIPT_BUCKET).upload(
        key, data, {"content-type": mime, "upsert": "false"})
    return key


def receipt_key_belongs_to(key: str, user_id: uuid.UUID) -> bool:
    """True if `key` is one this user uploaded.

    Without this the create/update endpoints would accept any key at all, and a
    user could attach another person's receipt to their own review and then
    read it back through the authorized path - turning the fix into a new hole.
    """
    if not key or "/" not in key:
        return False
    return key.split("/", 1)[0] == str(user_id)


def signed_receipt_url(key: str, expires_in: int) -> str | None:
    """A short-lived signed URL for an already-authorized caller, or None.

    Call this only after deciding the caller may see the object. It is
    deliberately not cached, stored, or logged: the returned string is a
    bearer credential for the lifetime of `expires_in`.

    None when the object is not there - a row can outlive its object, and the
    honest answer to "show me this receipt" is then "there is nothing to show",
    not a 500 that reads like the endpoint is broken.
    """
    try:
        signed = get_service_client().storage.from_(RECEIPT_BUCKET).create_signed_url(
            key, expires_in)
    except Exception:  # noqa: BLE001
        return None
    url = signed["signedURL"] if isinstance(signed, dict) else signed.signedURL
    if url.startswith("http"):
        return url
    base = str(get_service_client().storage._client.base_url).rstrip("/")  # noqa: SLF001
    return f"{base}{url}"


def receipt_exists(key: str) -> bool:
    """Whether the object is actually present in the private bucket."""
    folder, _, name = key.rpartition("/")
    try:
        listing = get_service_client().storage.from_(RECEIPT_BUCKET).list(folder)
    except Exception:  # noqa: BLE001
        return False
    return any((getattr(o, "name", None) or o.get("name")) == name for o in listing)


def delete_receipt_object(key: str) -> None:
    """Best-effort removal. A stale object is waste, not a correctness problem."""
    try:
        get_service_client().storage.from_(RECEIPT_BUCKET).remove([key])
    except Exception:  # noqa: BLE001
        pass
