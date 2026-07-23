"""Avatar upload validation.

Supabase Storage itself is not exercised here — these tests pin OUR rules:
the type is sniffed from magic bytes rather than trusted from the client, and
the size cap is enforced before anything is uploaded.
"""

from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.services import storage

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 64
GIF = b"GIF89a" + b"\x00" * 64


def test_sniffed_type_wins_over_declared_type():
    # A client claiming image/png over JPEG bytes must resolve to jpeg.
    assert storage.sniff_image_type(JPEG) == "image/jpeg"
    assert storage.sniff_image_type(PNG) == "image/png"
    assert storage.sniff_image_type(WEBP) == "image/webp"


def test_riff_that_is_not_webp_is_not_an_image():
    riff_wav = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 64
    assert storage.sniff_image_type(riff_wav) is None


def test_non_image_is_rejected():
    with pytest.raises(AppError) as exc:
        storage.validate_avatar(GIF)
    assert exc.value.code == "unsupported_media_type"


def test_oversize_is_rejected():
    too_big = PNG + b"\x00" * (5 * 1024 * 1024)
    with pytest.raises(AppError) as exc:
        storage.validate_avatar(too_big)
    assert exc.value.code == "file_too_large"


def test_empty_upload_is_rejected():
    with pytest.raises(AppError) as exc:
        storage.validate_avatar(b"")
    assert exc.value.code == "unsupported_media_type"


def test_valid_images_pass():
    assert storage.validate_avatar(PNG) == "image/png"
    assert storage.validate_avatar(JPEG) == "image/jpeg"
    assert storage.validate_avatar(WEBP) == "image/webp"
