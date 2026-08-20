"""Product images are seeded from manufacturers' press pages, which are huge.

One arrived at 1801x1800 and 887 KB, for a card that renders it a few hundred
pixels wide, and the homepage carries five of them - so the first page of a
review site aimed at Filipino mobile shoppers was moving 1.3 MB of images whose
detail nobody could see. After downscaling: 419 KB, and no visible difference
at the size they are displayed.

The alpha check is the part worth testing. Press images are often RGBA with a
channel that is opaque everywhere - a photo on white, saved with transparency
it never uses - and treating "has a channel" as "must stay PNG" kept one at
172 KB when the same picture is 40 KB as a JPEG.
"""

from __future__ import annotations

import io

import pytest

PIL = pytest.importorskip("PIL", reason="Pillow is not installed")
from PIL import Image  # noqa: E402

from scripts.seed_product_images import MAX_IMAGE_EDGE, _uses_transparency, downscale  # noqa: E402


def png(size=(1800, 1800), mode="RGB", alpha=255) -> bytes:
    img = Image.new(mode, size, (200, 120, 60) if mode == "RGB" else (200, 120, 60, alpha))
    # Noise, so the encoder cannot make a flat image trivially small and hide
    # whether the resize actually happened.
    for x in range(0, size[0], 7):
        for y in range(0, size[1], 11):
            img.putpixel((x, y), (x % 256, y % 256, (x + y) % 256)
                         if mode == "RGB" else (x % 256, y % 256, (x + y) % 256, alpha))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def dimensions(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as img:
        return img.size


class TestTransparencyDetection:

    def test_an_opaque_alpha_channel_does_not_count(self):
        with Image.open(io.BytesIO(png(mode="RGBA", alpha=255))) as img:
            assert _uses_transparency(img) is False

    def test_a_used_alpha_channel_does(self):
        with Image.open(io.BytesIO(png(mode="RGBA", alpha=128))) as img:
            assert _uses_transparency(img) is True

    def test_rgb_has_no_alpha_at_all(self):
        with Image.open(io.BytesIO(png(mode="RGB"))) as img:
            assert _uses_transparency(img) is False


class TestDownscale:

    def test_a_large_image_is_reduced(self):
        original = png((1800, 1800))
        out = downscale(original)
        assert len(out) < len(original)
        assert max(dimensions(out)) <= MAX_IMAGE_EDGE

    def test_aspect_ratio_survives(self):
        out = downscale(png((1600, 800)))
        w, h = dimensions(out)
        assert max(w, h) <= MAX_IMAGE_EDGE
        assert abs((w / h) - 2.0) < 0.02

    def test_an_opaque_png_becomes_a_jpeg(self):
        """Where most of the saving comes from."""
        out = downscale(png((1200, 1200), mode="RGBA", alpha=255))
        with Image.open(io.BytesIO(out)) as img:
            assert img.format == "JPEG"

    def test_real_transparency_stays_png(self):
        out = downscale(png((1200, 1200), mode="RGBA", alpha=64))
        with Image.open(io.BytesIO(out)) as img:
            assert img.format == "PNG"

    def test_a_small_image_is_left_alone(self):
        small = png((400, 400))
        assert downscale(small) == small

    def test_garbage_is_returned_unchanged(self):
        """A heavy image beats a missing one, so a bad decode must not lose it."""
        junk = b"not an image at all"
        assert downscale(junk) == junk

    def test_the_result_never_grows(self):
        for size in ((900, 900), (801, 400), (1800, 30)):
            original = png(size)
            assert len(downscale(original)) <= len(original), size
