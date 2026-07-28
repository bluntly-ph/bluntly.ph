# Frontend Follow-Ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the four open items in `FRONTEND_MILESTONES.md:101-110` — remove the seller surface, give products real images, ship bookmarks, and raise the legal copy.

**Architecture:** Four independent phases against the existing FastAPI + SQLAlchemy 2.0 backend and Next 16 App Router frontend. Product images are populated by a one-off script outside the application package, never by the running system; the moderator supplies images from then on. Bookmarks follow the existing `ReviewVote` model/service/route pattern exactly.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · Alembic · Postgres (Supabase) · pytest · Next.js 16 App Router (Turbopack) · React 19 · Tailwind v4

**Spec:** `docs/superpowers/specs/2026-07-28-frontend-followups-design.md`

## Global Constraints

- Migrations are sequential and named `NNNN_short_name.py`; `revision` equals the filename stem, `down_revision` is the previous stem. Next free number is `0019`.
- Nothing that resembles a scraping dependency may enter `backend/app/` — `M3_TEST_PLAN.md:97` check D9 greps for `scrapy|selenium|playwright|proxy_rotation`. The seed script lives in `backend/scripts/` and uses stdlib `html.parser` only.
- Content type is sniffed from magic bytes and **never** trusted from a response header (`backend/app/services/storage.py:8-11`).
- Money is string-decimal. "Buy it here" always routes through `/r/{id}`, never a raw affiliate URL.
- Frontend server components fetch via `lib/api/client.ts`; client mutations go through the BFF proxy `app/api/bff/[...path]`.
- Read the relevant guide in `node_modules/next/dist/docs/` before writing Next code — this is not the Next.js in your training data.
- Backend tests run from `backend/` with `pytest`. Do not run the full suite on Windows without a file target; it has timed out at >6 minutes before.

---

# Phase 1 — Remove the seller surface

Owner decision 2026-07-28: sellers go entirely, backend included.

### Task 1: Remove the frontend seller surface

**Files:**
- Delete: `app/sellers/[id]/page.tsx`
- Delete: `components/seller/SellerReviewForm.tsx`
- Delete: `lib/sellers.ts`

**Interfaces:**
- Consumes: nothing
- Produces: nothing — these files have no importers

- [ ] **Step 1: Confirm nothing imports them**

Run: `grep -rn "lib/sellers\|SellerReviewForm\|sellers/" app components lib --include=*.ts --include=*.tsx`
Expected: matches only inside the three files being deleted, plus `lib/api-types.d.ts` (generated, left alone until Task 3).

- [ ] **Step 2: Delete the files**

```bash
rm -r "app/sellers" "components/seller" "lib/sellers.ts"
```

- [ ] **Step 3: Verify the build**

Run: `npm run build`
Expected: succeeds; the printed route table contains no `/sellers` entry.

- [ ] **Step 4: Commit**

```bash
git add -A app components lib
git commit -m "refactor(fe): remove the unlinked seller surface"
```

---

### Task 2: Remove the backend seller surface

**Files:**
- Delete: `backend/app/api/v1/routes/sellers.py`
- Delete: `backend/app/models/seller_review.py`
- Delete: `backend/app/schemas/seller.py`
- **Edit, do NOT delete:** `backend/app/services/trust_rating_service.py` — see the split below
- Delete: `backend/tests/test_sellers_api.py`
- Modify: `backend/app/api/v1/router.py:8-22` (import list) and `:33` (`include_router`)
- Modify: `backend/app/models/__init__.py` — drop the `seller_review` import

**Interfaces:**
- Consumes: nothing
- Produces: an `api_v1_router` with no seller routes

- [ ] **Step 1: Find every reference before deleting**

Run: `grep -rn "seller" backend/app backend/tests --include=*.py`
Expected: a bounded list. Anything outside the five files above (for example a trust-service import) must be resolved in this task, not left dangling.

- [ ] **Step 2: Delete the seller-only modules**

```bash
git rm backend/app/api/v1/routes/sellers.py \
       backend/app/models/seller_review.py \
       backend/app/schemas/seller.py \
       backend/tests/test_sellers_api.py
```

- [ ] **Step 2b: Split `trust_rating_service.py` — do not delete it**

This module serves **two** features. Product trust is a surviving M2 deliverable consumed by `review_service.py:59-60`, `products.py:24,31`, and the nightly sweep in `workers/tasks.py:29-40`. Deleting the file breaks it.

**Keep:** `_conflict` (if still referenced), `recompute_product_trust`, `product_low_trust`.

**Remove:** `recompute_seller_trust`, `seller_or_404`, `create_seller_review`, `list_seller_reviews`, `seller_low_trust`, `seller_review_count`.

**Edit:** `recompute_all_trust_ratings` currently recomputes both and returns a dict covering each. Drop its seller half and the corresponding dict key, then update `workers/tasks.py:29-40` to match the new return shape — a stale key there is a silent nightly-job failure.

**Rewrite the module docstring.** It currently opens "Product & seller Wilson trust ratings + seller reviews (M2 slice 4)" and documents the seller publication-gate deviation. Both become false.

Keep the filename as-is; renaming would churn every importer for no functional gain.

- [ ] **Step 2c: Verify product trust still works**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_trust.py tests/test_trust_api.py -q`
Expected: PASS. If a test covered *seller* trust specifically, remove that test; if it covered *product* trust, it must still pass unchanged.

- [ ] **Step 3: Unregister the router**

In `backend/app/api/v1/router.py`, remove `sellers,` from the import tuple and delete the line `api_v1_router.include_router(sellers.router)`.

- [ ] **Step 4: Verify the app still imports**

Run: `cd backend && python -c "from app.main import app; print(len(app.routes))"`
Expected: prints a route count, no ImportError.

- [ ] **Step 5: Run the affected tests**

Run: `cd backend && pytest tests/test_openapi_contract.py tests/test_trust.py tests/test_trust_api.py -q`
Expected: PASS. If `test_trust*` asserted seller trust ratings, update those assertions here — the trust *score* for reviewers stays; only seller ratings go.

- [ ] **Step 6: Regenerate the OpenAPI schema**

Run: `cd backend && python -c "import json;from app.main import app;json.dump(app.openapi(),open('../docs/openapi.json','w'),indent=2)"`
Expected: `docs/openapi.json` no longer contains `/sellers`.

- [ ] **Step 7: Commit**

```bash
git add -A backend docs/openapi.json
git commit -m "refactor(api): remove seller ratings surface (owner decision)"
```

---

### Task 3: Regenerate frontend API types and sweep the seller remnants

**Files:**
- Modify: `lib/api-types.d.ts` (generated from `docs/openapi.json`)
- Modify: `backend/app/core/config.py` — remove `seller_trust_visibility_threshold`
- Modify: `backend/app/schemas/user.py` — remove `SellerProfileOut`
- Modify: `backend/app/main.py:35` — stale description prose
- Modify: `backend/app/models/moderation.py:7` — stale docstring example

- [ ] **Step 1: Regenerate the types**

Run: `npm run gen:api`

Use the package script, not a raw `npx` invocation — the script is the project's canonical command (`package.json:11`).
Expected: `/api/v1/sellers/...` paths (previously at `lib/api-types.d.ts:575,593`) are gone.

- [ ] **Step 2: Remove the dead seller config and schema**

Task 2 left these deliberately, as they were out of its brief's scope. The owner's decision is that sellers are gone entirely, so they go now.

- `backend/app/core/config.py` — delete the `seller_trust_visibility_threshold` setting. Grep for it first: if anything still reads it, resolve that too.
- `backend/app/schemas/user.py` — delete the `SellerProfileOut` class. Grep for it first; it should have no importers now that `routes/sellers.py` is gone.

- [ ] **Step 3: Fix the two stale prose references**

- `backend/app/main.py:35` reads "Verified product & seller review platform..." — drop "& seller".
- `backend/app/models/moderation.py:7` lists `seller_reviews` as a moderation-target example — replace it with a target that still exists.

These are cosmetic, but the FastAPI description at `main.py:35` is published in the OpenAPI schema and visible to anyone reading the API docs.

- [ ] **Step 4: Verify**

Run: `npx tsc --noEmit`
Expected: no errors.

Run: `cd backend && .venv/Scripts/python.exe -c "from app.main import app; print(len(app.routes))"`
Expected: a route count, no ImportError.

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_openapi_contract.py -q`
Expected: PASS.

- [ ] **Step 5: Regenerate the schema once more**

`main.py:35` feeds the OpenAPI description, so `docs/openapi.json` must be regenerated after editing it:

```bash
cd backend && .venv/Scripts/python.exe -c "import json;from app.main import app;json.dump(app.openapi(),open('../docs/openapi.json','w'),indent=2)"
```

Then re-run `npm run gen:api` so the committed types match the committed schema.

- [ ] **Step 6: Commit**

```bash
git add lib/api-types.d.ts backend/app docs/openapi.json
git commit -m "chore: regenerate API types and sweep seller remnants"
```

---

### Task 4: (moved) — the seller table drop is **Task 16**, at the end of this plan

The destructive migration is deliberately the **last** migration in the chain
(`0021_drop_seller_reviews`), not the first.

Reason: it is gated on owner approval, and a gate at `0019` would block
`alembic upgrade head` for the product-image and bookmark migrations that follow —
stalling Phases 2 and 3 behind an approval that has nothing to do with them. Ordering it
last makes the gate cost nothing.

Phase 1 therefore ends with the code and documentation removed and the table still present.
That is a deliberate, temporary state: the API and model are gone, so nothing reads the
table.

---

### Task 4b: Repair the milestone verification script

**Files:**
- Modify: `backend/scripts/verify_milestones.py:203-218`

`verify_milestones.py` is one of the four commands in the owner's M1–M3 production verification protocol. Seller removal broke it: it `POST`s to `/api/v1/sellers/{id}/reviews`, which no longer exists, so the M2 run now fails partway. This is a working-tool regression, not cosmetic.

- [ ] **Step 1: Remove the seller trust check, keep the product one**

At `:203-211`, delete the seller block entirely — the `m2seller` registration, the `role: seller` patch, the seller-review `POST`, the profile `GET`, and the `"M2: Wilson trust rating for SELLERS + dimension averages"` check.

**Keep** `"M2: Wilson trust rating for PRODUCTS"` at `:212-213` — product trust survives and this check must still pass.

- [ ] **Step 2: Fix the threshold check**

At `:214-218`, drop the trailing `and hasattr(settings, "seller_trust_visibility_threshold")` clause. That setting was deleted in Task 3, so the condition is now permanently False and the check would fail. Leave the `product_trust_visibility_threshold` clause intact.

- [ ] **Step 3: Verify the script runs**

Run: `cd backend && .venv/Scripts/python.exe scripts/verify_milestones.py`

Expected: it completes and the M2 section passes. Record the new total check count — it drops by exactly one (the removed SELLERS check).

If the script requires a live database or environment this run cannot reach, say so plainly in the report and confirm correctness by inspection instead. Do not fake a pass.

- [ ] **Step 4: Report the count change**

The owner's documented verification counts (referenced in `docs/MILESTONES.md` and the memory of a "159/49/59 green" run) include this check. Report the old and new counts so the documentation can be corrected — do not edit those docs in this task.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/verify_milestones.py
git commit -m "fix(scripts): drop seller checks from milestone verification"
```

---

### Task 5: Record the withdrawal in the documentation

**Files:**
- Modify: `docs/MILESTONES.md`, `docs/BACKEND_CAPSTONE_PAPER.md`, `docs/schema.md`, `docs/ARCHITECTURE_AS_BUILT.md`, `docs/FRONTEND_MILESTONES.md:102-105`

- [ ] **Step 1: Add a withdrawal note, do not delete the milestone**

In each document, where seller trust ratings are described as delivered, keep the description and append:

> **Withdrawn 2026-07-28 (owner decision).** Seller trust ratings were built and verified in M2, then removed: bluntly.ph is an affiliate-review platform, not a seller directory. The frontend, API, model and table were removed; `0019_drop_seller_reviews` drops the data.

A capstone that documents a scope change defends better than one with a milestone quietly missing.

- [ ] **Step 2: Update the frontend non-goal note**

Replace the `/sellers` bullet at `FRONTEND_MILESTONES.md:102-105` with a statement that the surface is fully removed, referencing the migration.

- [ ] **Step 2b: Correct the M2 verification check count**

`backend/scripts/verify_milestones.py` dropped from **49 checks to 48** — the "M2: Wilson trust rating for SELLERS + dimension averages" check went with the feature (Task 4b, commit `b0f8ba0`).

Grep the docs for the old figure and correct every occurrence:

```bash
grep -rn "49" docs/MILESTONES.md docs/M2_TEST_PLAN.md docs/PRODUCTION.md docs/LOCAL_TESTING_GUIDE.md
```

Only change counts that genuinely refer to the milestone-verification total — `49` appears in other contexts and a blind replace would corrupt them. Where a count is stated, note the reason for the change alongside it rather than silently editing the number.

Also add a caveat wherever the verification protocol is documented: the repaired script has been verified by inspection but **not yet executed against a live environment**, so the 48 figure is expected rather than observed. Remove that caveat once someone runs it for real.

- [ ] **Step 3: Commit**

```bash
git add docs
git commit -m "docs: record seller ratings as built-then-withdrawn"
```

---

# Phase 2 — Product images

### Task 6: Migration `0019` and model columns

**Files:**
- Create: `backend/alembic/versions/0019_product_image.py`
- Modify: `backend/app/models/product.py` (add three columns to `Product`)
- Modify: `backend/app/models/enums.py` (add `ImageSource`)

**Interfaces:**
- Produces: `Product.image_url: str | None`, `Product.image_source: ImageSource`, `Product.image_fetched_at: datetime | None`; `ImageSource` with members `seeded`, `moderator`, `none`

- [ ] **Step 1: Add the enum**

In `backend/app/models/enums.py`:

```python
class ImageSource(str, enum.Enum):
    seeded = "seeded"        # one-off backfill script, 2026-07-28
    moderator = "moderator"  # supplied by a human at link-attach time
    none = "none"            # no image resolved
```

- [ ] **Step 2: Add the columns to the model**

In `backend/app/models/product.py`, inside `Product`, after `source_url`:

```python
    # Product listing imagery. Distinct from a review's proof photo: this is the
    # merchant's picture of the item, not evidence that a reviewer owns one.
    image_url: Mapped[str | None] = mapped_column(Text)
    image_source: Mapped[ImageSource] = mapped_column(
        Enum(ImageSource, name="image_source"),
        default=ImageSource.none, nullable=False,
        server_default=ImageSource.none.value,
    )
    image_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Add `DateTime` to the `sqlalchemy` import block and `datetime` to the `datetime` import, and `ImageSource` to the `app.models.enums` import.

- [ ] **Step 3: Write the migration**

```python
"""products.image_url / image_source / image_fetched_at

Product listing imagery, so the feed stops rendering hue placeholders. Populated
once by scripts/seed_product_images.py and thereafter by moderators; the running
application never fetches a URL.

Revision ID: 0019_product_image
Revises: 0018_user_interests
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_product_image"
down_revision = "0018_user_interests"
branch_labels = None
depends_on = None

_IMAGE_SOURCE = sa.Enum("seeded", "moderator", "none", name="image_source")


def upgrade() -> None:
    _IMAGE_SOURCE.create(op.get_bind(), checkfirst=True)
    op.add_column("products", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("products", sa.Column(
        "image_source", _IMAGE_SOURCE, nullable=False, server_default="none"))
    op.add_column("products", sa.Column(
        "image_fetched_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "image_fetched_at")
    op.drop_column("products", "image_source")
    op.drop_column("products", "image_url")
    _IMAGE_SOURCE.drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 4: Apply and verify**

Run: `cd backend && alembic upgrade head && python -c "from app.models.product import Product; print(Product.image_source)"`
Expected: upgrade succeeds, prints the column.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models backend/alembic/versions/0019_product_image.py
git commit -m "feat(db): product listing image columns"
```

---

### Task 7: Product image upload helper

**Files:**
- Modify: `backend/app/services/storage.py`
- Test: `backend/tests/test_product_image.py`

**Interfaces:**
- Consumes: `sniff_image_type(data) -> str | None`, `_extension_for(mime) -> str` from `storage.py`
- Produces: `PRODUCT_BUCKET: str`, `MAX_PRODUCT_IMAGE_BYTES: int`, `validate_product_image(data: bytes) -> str`, `upload_product_image(product_id: uuid.UUID, data: bytes) -> str`

- [ ] **Step 1: Write the failing test**

```python
import uuid
import pytest
from app.core.errors import AppError
from app.services.storage import validate_product_image, MAX_PRODUCT_IMAGE_BYTES

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
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd backend && pytest tests/test_product_image.py -q`
Expected: FAIL, ImportError on `validate_product_image`.

- [ ] **Step 3: Implement**

Append to `backend/app/services/storage.py`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && pytest tests/test_product_image.py -q`
Expected: 3 passed.

- [ ] **Step 5: Create the bucket**

In the Supabase dashboard create a **public** bucket named `product-images`. Public because the images are served directly to anonymous readers.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/storage.py backend/tests/test_product_image.py
git commit -m "feat(storage): product image validation and upload"
```

---

### Task 8: The one-off seed script

**Files:**
- Create: `backend/scripts/seed_product_images.py`
- Create: `backend/scripts/__init__.py` (empty)
- Test: `backend/tests/test_seed_product_images.py`

**Interfaces:**
- Consumes: `upload_product_image` (Task 7), `Product.image_url` (Task 6)
- Produces: `is_public_host(host: str) -> bool`, `extract_og_image(html: str, base_url: str) -> str | None`, `resolve_image(url: str) -> bytes | None`

> Lives in `backend/scripts/`, outside the application package, so it stays clear of the D9 grep surface and nothing in the request path can import it.

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from scripts.seed_product_images import is_public_host, extract_og_image


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "10.0.0.5",
                                  "192.168.1.1", "169.254.169.254", "::1"])
def test_rejects_private_hosts(host):
    """SSRF guard: source_url is user-submitted and we fetch from inside our infra."""
    assert is_public_host(host) is False


def test_accepts_public_host():
    assert is_public_host("shopee.ph") is True


def test_extracts_og_image():
    html = '<meta property="og:image" content="https://cdn.example.com/a.jpg">'
    assert extract_og_image(html, "https://shop.example.com/p/1") == "https://cdn.example.com/a.jpg"


def test_falls_back_to_twitter_image():
    html = '<meta name="twitter:image" content="https://cdn.example.com/b.jpg">'
    assert extract_og_image(html, "https://shop.example.com/p/1") == "https://cdn.example.com/b.jpg"


def test_resolves_relative_image_url():
    html = '<meta property="og:image" content="/img/c.jpg">'
    assert extract_og_image(html, "https://shop.example.com/p/1") == "https://shop.example.com/img/c.jpg"


def test_returns_none_when_absent():
    assert extract_og_image("<html><body>challenge page</body></html>", "https://x.test/") is None
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd backend && pytest tests/test_seed_product_images.py -q`
Expected: FAIL, ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
"""One-off backfill of products.image_url from listing Open Graph tags.

Run once, by hand, by the owner. NOT imported by the application and NOT wired
into any request path, worker, or deploy step: the running platform performs no
automated fetch of a product URL, and that property is load-bearing (see the
anti-scraping mandate in docs/MILESTONES.md).

Scope: reads the og:image meta tag only. No listing, price, or commission data
is extracted, no headless browser, no proxy rotation, no marketplace API.
Expect partial success — bot-hostile listings return a challenge page with no
usable tag, and those products fall to the moderator path.

Usage:  cd backend && python -m scripts.seed_product_images --limit 50
        cd backend && python -m scripts.seed_product_images --dry-run
"""
from __future__ import annotations

import argparse
import ipaddress
import socket
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

from app.db.session import SessionLocal
from app.models.enums import ImageSource
from app.models.product import Product
from app.services.storage import upload_product_image

USER_AGENT = "bluntly.ph/1.0 (+https://www.bluntly.ph)"
MAX_HTML_BYTES = 512 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
TIMEOUT_S = 5
DELAY_S = 2.0


def is_public_host(host: str) -> bool:
    """False for anything that resolves into a private range.

    The URL comes from user submission, and this script runs inside our
    network, so a crafted source_url is an SSRF vector without this check.
    """
    host = host.strip("[]")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


class _MetaImageParser(HTMLParser):
    """Pulls og:image / twitter:image out of a document. Stdlib only, by policy."""

    def __init__(self) -> None:
        super().__init__()
        self.og: str | None = None
        self.twitter: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        key = a.get("property", "").lower() or a.get("name", "").lower()
        content = a.get("content", "")
        if not content:
            return
        if key == "og:image" and self.og is None:
            self.og = content
        elif key == "twitter:image" and self.twitter is None:
            self.twitter = content


def extract_og_image(html: str, base_url: str) -> str | None:
    parser = _MetaImageParser()
    parser.feed(html)
    found = parser.og or parser.twitter
    return urllib.parse.urljoin(base_url, found) if found else None


def _get(url: str, max_bytes: int) -> bytes | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    if not is_public_host(parsed.hostname):
        return None
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.read(max_bytes + 1)[:max_bytes]
    except Exception:
        return None


def resolve_image(url: str) -> bytes | None:
    """Listing URL -> image bytes, or None. Never raises."""
    page = _get(url, MAX_HTML_BYTES)
    if page is None:
        return None
    image_url = extract_og_image(page.decode("utf-8", "replace"), url)
    if image_url is None:
        return None
    return _get(image_url, MAX_IMAGE_BYTES)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    hits = misses = 0
    with SessionLocal() as db:
        products = (db.query(Product)
                      .filter(Product.image_url.is_(None),
                              Product.source_url.isnot(None))
                      .limit(args.limit).all())
        for product in products:
            print(f"[fetch] {product.id} {product.source_url}")
            data = resolve_image(product.source_url)
            if data is None:
                misses += 1
                print("  -> no usable og:image (moderator will supply)")
            elif args.dry_run:
                hits += 1
                print(f"  -> would upload {len(data)} bytes")
            else:
                product.image_url = upload_product_image(product.id, data)
                product.image_source = ImageSource.seeded
                product.image_fetched_at = datetime.now(timezone.utc)
                db.commit()
                hits += 1
                print(f"  -> {product.image_url}")
            time.sleep(DELAY_S)

    print(f"\nresolved {hits}, unresolved {misses} of {hits + misses}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && pytest tests/test_seed_product_images.py -q`
Expected: 6 passed. `test_rejects_private_hosts` is the one that matters — if it fails, do not run the script.

- [ ] **Step 5: Confirm D9 still passes**

Run: `grep -ri "scrapy\|selenium\|playwright\|proxy_rotation" backend/app`
Expected: no hits.

- [ ] **Step 6: Dry-run before touching data**

Run: `cd backend && python -m scripts.seed_product_images --dry-run --limit 5`
Expected: prints per-product hit/miss and a summary. Report the hit rate — a low rate is the expected Shopee outcome, not a bug to chase.

- [ ] **Step 7: Commit**

```bash
git add backend/scripts backend/tests/test_seed_product_images.py
git commit -m "feat(scripts): one-off product image seeding from og:image"
```

---

### Task 9: Moderator image endpoint

**Files:**
- Modify: `backend/app/api/v1/routes/admin_referral.py`
- Modify: `backend/app/schemas/product.py`
- Test: `backend/tests/test_product_image_api.py`

**Interfaces:**
- Consumes: `upload_product_image` (Task 7), `ImageSource` (Task 6)
- Produces: `PATCH /api/v1/admin/products/{product_id}/image`

- [ ] **Step 1: Write the failing test**

```python
def test_moderator_sets_product_image(client, moderator_token, product):
    res = client.patch(
        f"/api/v1/admin/products/{product.id}/image",
        files={"file": ("p.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "image/png")},
        headers={"Authorization": f"Bearer {moderator_token}"},
    )
    assert res.status_code == 200
    assert res.json()["image_source"] == "moderator"


def test_non_moderator_is_refused(client, member_token, product):
    res = client.patch(
        f"/api/v1/admin/products/{product.id}/image",
        files={"file": ("p.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "image/png")},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert res.status_code == 403
```

Mirror the fixture names already used in `backend/tests/test_referral_api.py`; do not invent new ones.

- [ ] **Step 2: Run and watch it fail**

Run: `cd backend && pytest tests/test_product_image_api.py -q`
Expected: FAIL, 404 (route absent).

- [ ] **Step 3: Implement the route**

Add to `backend/app/api/v1/routes/admin_referral.py`, following the moderator dependency already used by `attach_link` at `:92`:

```python
@router.patch("/products/{product_id}/image", response_model=ProductOut,
              summary="Attach a product listing image (moderator)")
def set_product_image(product_id: uuid.UUID, file: UploadFile = File(...),
                      db: Session = Depends(get_db),
                      user: User = Depends(require_moderator)) -> ProductOut:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found.")
    product.image_url = upload_product_image(product.id, file.file.read())
    product.image_source = ImageSource.moderator
    product.image_fetched_at = datetime.now(timezone.utc)
    db.commit()
    return ProductOut.model_validate(product)
```

Add `image_url` and `image_source` to `ProductOut` in `backend/app/schemas/product.py`.

- [ ] **Step 4: Run the tests**

Run: `cd backend && pytest tests/test_product_image_api.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests/test_product_image_api.py
git commit -m "feat(api): moderator product image endpoint"
```

---

### Task 10: Render product images

**Files:**
- Modify: `next.config.ts`
- Modify: `components/review/ReviewCard.tsx:32-50`
- Modify: `components/review/ReviewDetail.tsx:123-140`
- Modify: `lib/reviews.ts:126-135`

- [ ] **Step 1: Read the Next image docs first**

Read `node_modules/next/dist/docs/01-app/03-api-reference/02-components/image.md:533-575`. `remotePatterns` accepts `new URL(...)` shorthand in Next 16.

- [ ] **Step 2: Allow the Supabase storage host**

In `next.config.ts`, inside `nextConfig`:

```ts
  images: {
    remotePatterns: [new URL("https://*.supabase.co/storage/v1/object/public/**")],
  },
```

CSP needs no change — `next.config.ts:21` already allows `https://*.supabase.co` in `img-src`. That is the reason images are cached into Supabase rather than hotlinked from a merchant CDN.

- [ ] **Step 3: Map the product image through**

In `lib/reviews.ts`, in `toCard` (around `:134`), set `imageUrl` from the product image, falling back to the review's own photo only if you deliberately want that. Keep `usablePhoto()` (`lib/reviews.ts:109`) guarding both.

- [ ] **Step 4: Relabel the proof photo**

`ReviewDetail.tsx:123` reads "The reviewer's proof photo, or a clean branded placeholder when none." Keep that slot reviewer-only and add the product image as a separate element with its own caption, so a merchant picture is never presented as ownership evidence.

- [ ] **Step 5: Verify**

Run: `npm run build && npm run dev`
Expected: build clean; a product with an image renders it; a product without one still shows the hue placeholder.

- [ ] **Step 6: Commit**

```bash
git add next.config.ts components lib
git commit -m "feat(fe): render product listing images"
```

---

### Task 10b: Record the seeding footnote

**Files:**
- Modify: `backend/app/models/product.py:3-5`
- Modify: `docs/ARCHITECTURE_AS_BUILT.md`

Implements spec §2.8. The anti-scraping mandate stands unchanged — this adds a factual footnote so the record is accurate, nothing more.

- [ ] **Step 1: Amend the model docstring**

`backend/app/models/product.py:3-5` currently reads "No automated fetch of the URL ever happens." That remains true of the application. Make it precise:

```
Manual-first canonicalization (§3.1): a product is submitted via `source_url`
with status `pending`; an admin sets the canonical name fields and flips it to
`canonicalized`. The application never fetches the URL.

Initial product images were backfilled once, on 2026-07-28, by a manually-run
script (`backend/scripts/seed_product_images.py`) reading the listing's Open
Graph image tag. That script is not imported by the application and is not part
of any request path. Images for products created since then are supplied by a
moderator by hand.
```

- [ ] **Step 2: Add the same note to `ARCHITECTURE_AS_BUILT.md`**

Beside the existing "no scraping, no marketplace API calls" claim at `:15`, which stays as written — it is still true.

- [ ] **Step 3: Confirm the mandate documents need no edit**

Re-read `docs/MILESTONES.md:118,127`, `docs/BACKEND_CAPSTONE_PAPER.md:61-65`, `docs/01-bluntly-ph-PRD.md:60,148`. Each describes the *running platform*, which still performs no automated fetch. Leave them unchanged. If any is worded so broadly that the seed script contradicts it, narrow that one sentence rather than weakening the mandate.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/product.py docs/ARCHITECTURE_AS_BUILT.md
git commit -m "docs: footnote the one-off product image backfill"
```

---

# Phase 3 — Bookmarks and Recent Reads

### Task 11: Bookmark model and migration `0020`

**Files:**
- Create: `backend/app/models/bookmark.py`
- Create: `backend/alembic/versions/0020_bookmarks.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Produces: `Bookmark` with `user_id: uuid.UUID`, `review_id: uuid.UUID`, unique on the pair

- [ ] **Step 1: Write the model, mirroring `ReviewVote` (`backend/app/models/vote.py:36-53`)**

```python
"""bookmarks — a reader's saved reviews.

Server-side because a saved review must survive a device change. Deliberately
paired with client-side Recent Reads (lib/recent-reads.ts), which is ephemeral
browsing history and stays in localStorage so no reading-history obligation is
incurred.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class Bookmark(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "bookmarks"
    __table_args__ = (
        UniqueConstraint("user_id", "review_id", name="uq_bookmark_once"),
        Index("ix_bookmarks_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )
```

- [ ] **Step 2: Write migration `0020_bookmarks.py`**

```python
"""bookmarks — reader's saved reviews

Revision ID: 0020_bookmarks
Revises: 0019_product_image
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020_bookmarks"
down_revision = "0019_product_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bookmarks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("user_id", "review_id", name="uq_bookmark_once"),
    )
    op.create_index("ix_bookmarks_user_id", "bookmarks", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_bookmarks_user_id", table_name="bookmarks")
    op.drop_table("bookmarks")
```

Check the `id` / `created_at` / `updated_at` column definitions against an existing migration that uses `UUIDPrimaryKey` + `Timestamps` and match them exactly — those mixins define the real defaults.

- [ ] **Step 3: Apply and verify**

Run: `cd backend && alembic upgrade head && alembic current`
Expected: `0020_bookmarks`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models backend/alembic/versions/0020_bookmarks.py
git commit -m "feat(db): bookmarks table"
```

---

### Task 12: Bookmark service and routes

**Files:**
- Create: `backend/app/services/bookmark_service.py`
- Create: `backend/app/api/v1/routes/bookmarks.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_bookmarks_api.py`

**Interfaces:**
- Consumes: `Bookmark` (Task 11)
- Produces: `POST /api/v1/reviews/{review_id}/bookmark`, `DELETE /api/v1/reviews/{review_id}/bookmark`, `GET /api/v1/me/bookmarks`

- [ ] **Step 1: Write the failing tests**

```python
def test_bookmark_then_list(client, member_token, published_review):
    h = {"Authorization": f"Bearer {member_token}"}
    assert client.post(f"/api/v1/reviews/{published_review.id}/bookmark", headers=h).status_code == 201
    listed = client.get("/api/v1/me/bookmarks", headers=h).json()
    assert [b["review_id"] for b in listed] == [str(published_review.id)]


def test_bookmarking_twice_is_idempotent(client, member_token, published_review):
    """A double-tap on a phone must not 500."""
    h = {"Authorization": f"Bearer {member_token}"}
    client.post(f"/api/v1/reviews/{published_review.id}/bookmark", headers=h)
    second = client.post(f"/api/v1/reviews/{published_review.id}/bookmark", headers=h)
    assert second.status_code in (200, 201)
    assert len(client.get("/api/v1/me/bookmarks", headers=h).json()) == 1


def test_delete_removes_it(client, member_token, published_review):
    h = {"Authorization": f"Bearer {member_token}"}
    client.post(f"/api/v1/reviews/{published_review.id}/bookmark", headers=h)
    assert client.delete(f"/api/v1/reviews/{published_review.id}/bookmark", headers=h).status_code == 204
    assert client.get("/api/v1/me/bookmarks", headers=h).json() == []


def test_anonymous_is_refused(client, published_review):
    assert client.post(f"/api/v1/reviews/{published_review.id}/bookmark").status_code == 401
```

- [ ] **Step 2: Run and watch them fail**

Run: `cd backend && pytest tests/test_bookmarks_api.py -q`
Expected: FAIL with 404.

- [ ] **Step 3: Implement the service**

```python
def add(db: Session, user_id: uuid.UUID, review_id: uuid.UUID) -> Bookmark:
    """Idempotent: a repeat bookmark returns the existing row, not an error."""
    existing = db.execute(
        select(Bookmark).where(Bookmark.user_id == user_id,
                               Bookmark.review_id == review_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    bookmark = Bookmark(user_id=user_id, review_id=review_id)
    db.add(bookmark)
    db.commit()
    return bookmark
```

```python
def remove(db: Session, user_id: uuid.UUID, review_id: uuid.UUID) -> None:
    """Also idempotent — deleting a bookmark that is not there is not an error."""
    db.execute(delete(Bookmark).where(Bookmark.user_id == user_id,
                                      Bookmark.review_id == review_id))
    db.commit()


def list_for(db: Session, user_id: uuid.UUID) -> list[Bookmark]:
    return list(db.execute(
        select(Bookmark).where(Bookmark.user_id == user_id)
                        .order_by(Bookmark.created_at.desc())
    ).scalars().all())
```

- [ ] **Step 4: Implement the routes and register the router**

Use the same authenticated-user dependency `backend/app/api/v1/routes/reviews.py` uses for vote endpoints — read it first rather than inventing one.

```python
router = APIRouter(tags=["bookmarks"])


@router.post("/reviews/{review_id}/bookmark", status_code=201,
             response_model=BookmarkOut, summary="Save a review")
def create(review_id: uuid.UUID, db: Session = Depends(get_db),
           user: User = Depends(require_user)) -> BookmarkOut:
    review = db.get(Review, review_id)
    if review is None or review.published_at is None:
        raise NotFoundError("Review not found.")
    return BookmarkOut.model_validate(bookmark_service.add(db, user.id, review_id))


@router.delete("/reviews/{review_id}/bookmark", status_code=204,
               summary="Unsave a review")
def destroy(review_id: uuid.UUID, db: Session = Depends(get_db),
            user: User = Depends(require_user)) -> None:
    bookmark_service.remove(db, user.id, review_id)


@router.get("/me/bookmarks", response_model=list[BookmarkOut],
            summary="The signed-in reader's saved reviews")
def index(db: Session = Depends(get_db),
          user: User = Depends(require_user)) -> list[BookmarkOut]:
    return [BookmarkOut.model_validate(b) for b in bookmark_service.list_for(db, user.id)]
```

Register with `api_v1_router.include_router(bookmarks.router)` in `backend/app/api/v1/router.py`. Define `BookmarkOut` (`id`, `review_id`, `created_at`) in a new `backend/app/schemas/bookmark.py`.

- [ ] **Step 5: Run the tests**

Run: `cd backend && pytest tests/test_bookmarks_api.py -q`
Expected: 4 passed.

- [ ] **Step 6: Regenerate the schema and types**

Run: `cd backend && python -c "import json;from app.main import app;json.dump(app.openapi(),open('../docs/openapi.json','w'),indent=2)"` then `npx openapi-typescript docs/openapi.json -o lib/api-types.d.ts`

- [ ] **Step 7: Commit**

```bash
git add backend docs/openapi.json lib/api-types.d.ts
git commit -m "feat(api): bookmarks"
```

---

### Task 13: Bookmark UI and Recent Reads

**Files:**
- Create: `components/review/BookmarkButton.tsx`
- Create: `app/saved/page.tsx`
- Create: `lib/recent-reads.ts`
- Create: `components/landing/RecentReads.tsx`
- Modify: `components/site/SiteHeader.tsx`, `components/review/ReviewDetail.tsx`, `app/page.tsx`

- [ ] **Step 1: `BookmarkButton`**

A client component posting through the BFF (`/api/bff/api/v1/reviews/{id}/bookmark`), optimistic toggle, reverting on failure. Follow `components/review/ReviewVoteBar.tsx` — it already does exactly this shape.

- [ ] **Step 2: `/saved`**

A server component calling `requireUser()` from `lib/dal.ts`, fetching `GET /api/v1/me/bookmarks`, rendering the existing `ReviewCard` grid, with an empty state pointing at `/search`.

- [ ] **Step 3: `lib/recent-reads.ts`**

```ts
const KEY = "bluntly.recent-reads";
const MAX = 10;

/** Ephemeral, device-local reading history. Deliberately not server-side:
 *  it carries no cross-device value and storing it would make us a tracker. */
export function pushRecentRead(id: string): void {
  if (typeof window === "undefined") return;
  const prior = readRecentReads().filter((x) => x !== id);
  localStorage.setItem(KEY, JSON.stringify([id, ...prior].slice(0, MAX)));
}

export function readRecentReads(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}
```

- [ ] **Step 4: Wire it up**

`ReviewDetail` calls `pushRecentRead(review.id)` in a client effect. `RecentReads` renders the rail on the landing page and returns `null` when the list is empty, so a first-time visitor sees nothing rather than an empty box.

- [ ] **Step 5: Verify**

Run: `npm run build`, then in the browser: bookmark a review, reload, confirm it persists; visit `/saved`; open two reviews and confirm the rail appears with no network call.

- [ ] **Step 6: Commit**

```bash
git add components app lib
git commit -m "feat(fe): bookmarks and recent reads"
```

---

# Phase 4 — Legal copy

### Task 14: Affiliate disclosure

**Files:**
- Create: `components/site/AffiliateDisclosure.tsx`
- Modify: `components/review/ReviewDetail.tsx`, `app/legal/page.tsx`

- [ ] **Step 1: Write the component**

A short, plain inline notice rendered adjacent to the "Buy it here" control:

> **How this link works.** bluntly.ph earns a commission when you buy through this link. It costs you nothing extra, and it does not change what a reviewer is allowed to say — reviewers are paid for reviews that pass moderation, not for positive ones.

The second sentence is the one that matters: on a platform that pays reviewers, disclosing the commission without disclosing the independence of the payment is only half the story.

- [ ] **Step 2: Surface it on review detail, not only in `/legal`**

A disclosure a reader never sees is not a disclosure.

- [ ] **Step 3: Verify and commit**

Run: `npm run build`

```bash
git add components app
git commit -m "feat(legal): affiliate disclosure on review detail"
```

---

### Task 15: Privacy, Terms, Guidelines

**Files:**
- Modify: `app/privacy/page.tsx`, `app/terms/page.tsx`, `app/guidelines/page.tsx`, `app/legal/page.tsx`

- [ ] **Step 1: Privacy — rewrite against RA 10173**

Required sections, each with real content, not headings:
- What is collected: email, display name, avatar, reviews and votes, **bookmarks** (Task 11), payout details (PayPal email), IP for vote rate-limiting (`backend` rate limiter keys on client IP)
- Why, per item, and the lawful basis
- Retention, cross-referenced to the existing PII retention schedule (`backend/app/services/retention_service.py`)
- Data-subject rights under RA 10173: access, correction, erasure, objection, data portability
- How to exercise them, and the National Privacy Commission as the complaint route
- Third parties: Supabase (hosting/storage), Vercel (hosting), Resend (email), PayPal (payouts)

- [ ] **Step 2: Terms and Guidelines**

Align with the actual review lifecycle: reviews are held for moderation and never auto-published; earnings depend on passing the earn-eligible gate; self-voting and double-voting are rejected; affiliate links are attached by moderators.

- [ ] **Step 3: No "pending counsel review" marker on the rendered pages**

Owner decision 2026-07-28. The caveat lives in the spec, internal only. Do not add a banner.

- [ ] **Step 4: Verify and commit**

Run: `npm run build` and confirm every footer link still resolves.

```bash
git add app
git commit -m "docs(legal): PH-specific privacy, terms and guidelines"
```

---

# Phase 5 — The destructive migration

### Task 16: Drop the seller tables — migration `0021`

> **GATE: this task writes the migration and STOPS. Do not run `alembic upgrade` without an explicit go-ahead from the owner.** It drops rows that no `git revert` brings back. Every other task in this plan is reversible; this one is not.

Runs last so the gate blocks nothing else. By this point the seller API, model, schema and frontend are already gone (Tasks 1-3), so nothing reads the table.

**Files:**
- Create: `backend/alembic/versions/0021_drop_seller_reviews.py`

**Interfaces:**
- Consumes: `0020_bookmarks` as `down_revision`

- [ ] **Step 1: Count what would be lost**

```sql
SELECT count(*) FROM seller_reviews;
```
Report the number to the owner. If it is non-trivial, stop and re-confirm before continuing.

- [ ] **Step 2: Take a retained backup**

```bash
pg_dump "$DATABASE_URL" -t seller_reviews -Fc -f seller_tables_20260728.dump
```
Store it outside the database. Confirm the file is non-empty before proceeding.

- [ ] **Step 3: Inspect the live table**

```sql
\d seller_reviews
```
The `downgrade` below must mirror the real column list, not a stub.

- [ ] **Step 4: Write the migration**

```python
"""drop seller_reviews

Seller trust ratings were delivered in M2 and withdrawn by owner decision on
2026-07-28: bluntly.ph is an affiliate-review platform, not a seller directory.
The table is dropped rather than orphaned so the schema stops implying a feature
that no longer exists.

Irreversible: downgrade recreates the structure but not the rows. Restore from
the pg_dump taken before upgrade if they are ever needed.

Revision ID: 0021_drop_seller_reviews
Revises: 0020_bookmarks
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021_drop_seller_reviews"
down_revision = "0020_bookmarks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("seller_reviews")


def downgrade() -> None:
    # Structure only — replace this column list with the real one from Step 3.
    op.create_table(
        "seller_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
```

- [ ] **Step 5: Verify it is well-formed without applying it**

Run: `cd backend && alembic heads`
Expected: a single head, `0021_drop_seller_reviews`.

- [ ] **Step 6: Commit the migration unapplied**

```bash
git add backend/alembic/versions/0021_drop_seller_reviews.py
git commit -m "feat(db): migration to drop seller_reviews (NOT YET APPLIED)"
```

- [ ] **Step 7: STOP — hand back to the owner for the apply decision**

Report the row count from Step 1 and the backup path from Step 2. Do not run `alembic upgrade head`.

---

## Final verification

- [ ] `cd backend && pytest -q` — record the new expected count (was 159; seller tests removed, product-image and bookmark tests added)
- [ ] `npm run build` — clean, no `/sellers` in the route table
- [ ] `grep -ri "scrapy\|selenium\|playwright\|proxy_rotation" backend/app` — no hits
- [ ] Prod smoke: `/`, `/search`, `/categories`, `/saved`, `/about`, `/faqs`, `/privacy`, `/guidelines` return 200; `/sellers/anything` returns 404
- [ ] `docs/FRONTEND_MILESTONES.md:101-110` follow-ups list updated to reflect what is now closed
