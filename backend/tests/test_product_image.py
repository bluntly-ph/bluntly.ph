"""Product image upload validation.

Same discipline as avatars: the type is sniffed from magic bytes rather than
trusted from a declared Content-Type, and the size cap is enforced before
anything is uploaded. This matters more here — a later task feeds this
helper bytes fetched from an arbitrary merchant URL, so the input is
genuinely untrusted.
"""

from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.services.storage import MAX_PRODUCT_IMAGE_BYTES, validate_product_image

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def test_validate_accepts_png():
    assert validate_product_image(PNG) == "image/png"


def test_validate_rejects_html_masquerading_as_image():
    with pytest.raises(AppError) as exc:
        validate_product_image(b"<!doctype html><html>gotcha</html>")
    assert exc.value.code == "unsupported_media_type"


def test_validate_rejects_oversize():
    with pytest.raises(AppError) as exc:
        validate_product_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_PRODUCT_IMAGE_BYTES)
    assert exc.value.code == "file_too_large"
