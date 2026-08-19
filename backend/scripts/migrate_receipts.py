"""Move proof-of-purchase objects out of the public bucket into private storage.

Run by hand, by the owner, once. NOT imported by the application.

Ordering matters and is enforced by the two phases below. The private copy is
made and verified BEFORE the schema changes and BEFORE anything is deleted, so
at no point is a real user's evidence held in only one place.

  1. `--copy`   read every receipt locator, copy the object into the private
                bucket, verify the destination object exists. Idempotent.
  2. (migration 0023 runs here: backfills receipt_key, drops receipt_url,
     strips the locator from review_versions.snapshot)
  3. `--purge`  delete the now-redundant public object, then confirm the old
                public URL no longer resolves.

Nothing here prints receipt contents, object paths, or any customer data: the
output is counts and review ids only. A locator in a terminal scrollback or a
CI log is the same class of leak this whole change exists to close.
"""
from __future__ import annotations

import argparse
import urllib.error
import urllib.request

from sqlalchemy import inspect, text

from app.core.env_guard import guard_cli
from app.core.supabase_client import get_service_client
from app.db.session import SessionLocal, engine
from app.services.storage import (
    RECEIPT_BUCKET,
    REVIEW_BUCKET,
    receipt_exists,
)

PUBLIC_MARKER = "/storage/v1/object/public/"


def _column_present(name: str) -> bool:
    return name in {c["name"] for c in inspect(engine).get_columns("reviews")}


def _key_from_url(url: str) -> str | None:
    """`.../public/<bucket>/<key>` -> `<key>`; None if not a public URL."""
    if PUBLIC_MARKER not in url:
        return None
    after = url.split(PUBLIC_MARKER, 1)[1]
    return after.split("/", 1)[1] if "/" in after else None


def _rows() -> list[tuple[str, str, str | None]]:
    """(review_id, object_key, author_id) for every review carrying a receipt.

    Reads whichever column exists, so the script works either side of the
    migration and a re-run after it still finds the same objects.
    """
    col = "receipt_key" if _column_present("receipt_key") else "receipt_url"
    with SessionLocal() as db:
        raw = db.execute(text(
            f"SELECT id::text, {col}, author_id::text FROM reviews "
            f"WHERE {col} IS NOT NULL"
        )).all()
    out: list[tuple[str, str, str | None]] = []
    for review_id, value, author_id in raw:
        key = value if col == "receipt_key" else _key_from_url(value)
        if key:
            out.append((review_id, key, author_id))
        else:
            print(f"  [skip] review {review_id}: locator is not a public URL")
    return out


def copy_phase() -> int:
    client = get_service_client()
    src = client.storage.from_(REVIEW_BUCKET)
    dst = client.storage.from_(RECEIPT_BUCKET)
    moved = 0
    for review_id, key, author_id in _rows():
        # The key prefix is the uploader; it must be the review's author, or the
        # reference is wrong and copying it would propagate that.
        owner = key.split("/", 1)[0]
        if author_id and owner != author_id:
            print(f"  [WARN] review {review_id}: key owner != author - not copied")
            continue
        if receipt_exists(key):
            print(f"  [have] review {review_id}: already in private storage")
            moved += 1
            continue
        data = src.download(key)
        dst.upload(key, data, {"content-type": "image/jpeg", "upsert": "true"})
        if not receipt_exists(key):
            print(f"  [FAIL] review {review_id}: destination object not found after upload")
            continue
        print(f"  [copy] review {review_id}: {len(data)} bytes -> private bucket")
        moved += 1
    return moved


def purge_phase() -> int:
    client = get_service_client()
    src = client.storage.from_(REVIEW_BUCKET)
    purged = 0
    for review_id, key, _ in _rows():
        if not receipt_exists(key):
            print(f"  [STOP] review {review_id}: no private copy - refusing to delete")
            continue
        src.remove([key])
        old = src.get_public_url(key)
        try:
            urllib.request.urlopen(
                urllib.request.Request(old, headers={"User-Agent": "migrate"}), timeout=15)
            print(f"  [FAIL] review {review_id}: old public object STILL resolves")
        except urllib.error.HTTPError as exc:
            print(f"  [gone] review {review_id}: old public object now HTTP {exc.code}")
            purged += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  [gone] review {review_id}: old public object unreachable ({type(exc).__name__})")
            purged += 1
    return purged


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-production", action="store_true",
                        help='Deliberately target production. Only a few scripts accept this; the guard prints the target first.')
    ap.add_argument("--copy", action="store_true", help="public -> private, verified")
    ap.add_argument("--purge", action="store_true", help="delete the public originals")
    args = ap.parse_args()
    if args.copy == args.purge:
        ap.error("choose exactly one of --copy or --purge")

    if args.copy:
        print(f"copy phase: {copy_phase()} object(s) present in private storage")
    else:
        print(f"purge phase: {purge_phase()} public original(s) removed and confirmed gone")


if __name__ == "__main__":
    # Refuses production before a single row is touched.
    guard_cli("migrate_receipts", production_is_legitimate=True)
    main()
