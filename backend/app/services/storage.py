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
MAX_AVATAR_BYTES = 5 * 1024 * 1024

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
    bucket.upload(path, data, {"content-type": mime, "upsert": "false"})
    return bucket.get_public_url(path)


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
        path, data, {"content-type": mime, "upsert": "true"})
    return client.storage.from_(PRODUCT_BUCKET).get_public_url(path)


REVIEW_BUCKET = "review-photos"
MAX_REVIEW_PHOTO_BYTES = 8 * 1024 * 1024


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
        path, data, {"content-type": mime, "upsert": "false"})
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
MAX_RECEIPT_BYTES = 8 * 1024 * 1024


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


def signed_receipt_url(key: str, expires_in: int) -> str:
    """A short-lived signed URL for an already-authorized caller.

    Call this only after deciding the caller may see the object. It is
    deliberately not cached, stored, or logged: the returned string is a
    bearer credential for the lifetime of `expires_in`.
    """
    signed = get_service_client().storage.from_(RECEIPT_BUCKET).create_signed_url(
        key, expires_in)
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
