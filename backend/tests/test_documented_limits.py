"""`docs/schema.md` states the storage caps. So does the code. They must agree.

schema.md is a spec document — the thing somebody reads to find out what the
system does without reading the system. It said 8 MB for review photos and
receipts long after the code moved to 4 MB, and nothing anywhere would have
noticed: a document cannot fail a test suite it is not part of.

The caps moved for a measured reason. The platform refuses a request body
somewhere between 3.0 MB and 4.4 MB with a bare 413 before any of our code
runs, so a higher cap is one the API can never enforce — the reader gets a
platform error page instead of a sentence explaining what went wrong.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from app.services.storage import (
    MAX_AVATAR_BYTES,
    MAX_PRODUCT_IMAGE_BYTES,
    MAX_RECEIPT_BYTES,
    MAX_REVIEW_PHOTO_BYTES,
)

SCHEMA_DOC = pathlib.Path(__file__).resolve().parents[2] / "docs" / "schema.md"

# bucket name in the doc -> the constant the code enforces
DOCUMENTED = {
    "avatars": MAX_AVATAR_BYTES,
    "product-images": MAX_PRODUCT_IMAGE_BYTES,
    "review-photos": MAX_REVIEW_PHOTO_BYTES,
    "review-receipts": MAX_RECEIPT_BYTES,
}


def documented_caps() -> dict[str, int]:
    """Parse the bucket table out of schema.md."""
    caps: dict[str, int] = {}
    for line in SCHEMA_DOC.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip().strip("*` ") for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        match = re.fullmatch(r"(\d+)\s*MB", cells[2])
        if match and cells[0] in DOCUMENTED:
            caps[cells[0]] = int(match.group(1)) * 1024 * 1024
    return caps


@pytest.mark.skipif(not SCHEMA_DOC.exists(), reason="docs not checked out")
def test_the_table_still_parses():
    """If the table's shape changes, the rest of this file goes quiet."""
    caps = documented_caps()
    assert set(caps) == set(DOCUMENTED), (
        f"parsed {sorted(caps)} from schema.md, expected {sorted(DOCUMENTED)} — "
        f"the bucket table changed shape and this test stopped checking")


@pytest.mark.skipif(not SCHEMA_DOC.exists(), reason="docs not checked out")
@pytest.mark.parametrize("bucket", sorted(DOCUMENTED))
def test_the_documented_cap_matches_the_code(bucket):
    documented = documented_caps()[bucket]
    enforced = DOCUMENTED[bucket]
    assert documented == enforced, (
        f"docs/schema.md says {bucket} is capped at "
        f"{documented // 1024 // 1024} MB; the code enforces "
        f"{enforced // 1024 // 1024} MB")


def test_the_function_facing_caps_stay_under_the_platform_limit():
    """Measured: the platform refuses somewhere between 3.0 MB and 4.4 MB.

    product-images is deliberately excluded — it is uploaded straight to
    Supabase Storage by a script and never crosses a serverless function.
    """
    platform_floor = 4.4 * 1024 * 1024
    for name, cap in (("avatar", MAX_AVATAR_BYTES),
                      ("review photo", MAX_REVIEW_PHOTO_BYTES),
                      ("receipt", MAX_RECEIPT_BYTES)):
        assert cap < platform_floor, (
            f"the {name} cap is {cap} bytes, at or above the platform's own "
            f"limit — the API can never enforce it and the reader gets a 413")
