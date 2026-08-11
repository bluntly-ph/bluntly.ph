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

    The allowance is larger than an avatar's because this is evidence, not
    decoration: a receipt photographed on a modern phone routinely clears 5 MB,
    and rejecting a *valid* proof of purchase is worse than storing a few extra
    megabytes. Same magic-byte discipline as everywhere else in this module —
    the browser's Content-Type is attacker-controlled.

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
    """Store a review photo and return its public URL.

    Keyed by uploader rather than by review: the photo is chosen while the
    review is still being written and has no id yet. Binding it to the author
    keeps the path attributable, which is what matters when a proof-of-purchase
    image is later disputed.
    """
    mime = validate_review_photo(data)
    path = f"{user_id}/{uuid.uuid4().hex}.{_extension_for(mime)}"
    client = get_service_client()
    client.storage.from_(REVIEW_BUCKET).upload(
        path, data, {"content-type": mime, "upsert": "false"})
    return client.storage.from_(REVIEW_BUCKET).get_public_url(path)
