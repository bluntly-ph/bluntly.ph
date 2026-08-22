"""Re-stamp existing public images with a cacheable `Cache-Control`.

Every object uploaded before the storage fix carries `Cache-Control: no-cache`,
because `storage3` applies its own default only when `file_options` is omitted
entirely - and every upload site passes a partial dict, which silently discards
it. New uploads are fixed at the source (`storage.PUBLIC_IMAGE_MAX_AGE`); this
repairs what is already there.

Why it matters, measured on production 2026-08-23: the product image on
`/search` is that page's LCP element, and with `no-cache` it was refetched in
full (120,455 B, CF-Cache-Status MISS) on every load - 9.25 s under Lighthouse
throttling.

The bytes are preserved exactly. Each object is downloaded, re-PUT to the same
path (so its public URL and every database reference stay valid), then
downloaded again and compared by SHA-256. A mismatch is reported loudly and
stops the run rather than continuing through the rest.

Receipts are deliberately not touched: private evidence reached through a
short-lived signed URL should not become cacheable.

Usage:
    cd backend && python -m scripts.backfill_image_cache_headers          # dry run
    cd backend && python -m scripts.backfill_image_cache_headers --apply
"""

from __future__ import annotations

import argparse
import hashlib

from app.core.supabase_client import get_service_client
from app.services.storage import (
    AVATAR_BUCKET,
    PRODUCT_BUCKET,
    PUBLIC_IMAGE_MAX_AGE,
    REVIEW_BUCKET,
)

#: Public image buckets only. `review-receipts` is excluded on purpose.
BUCKETS = (PRODUCT_BUCKET, REVIEW_BUCKET, AVATAR_BUCKET)

#: Objects whose stored cacheControl is any of these need re-stamping.
_STALE = {"no-cache", "", None}


def _walk(bucket, prefix: str = "") -> list[str]:
    """Every object path under `prefix`, depth-first.

    Storage `list` is one level at a time: a folder comes back as an entry with
    no `id`, and its children are only visible by listing into it. A flat list
    would silently return nothing here, because every object lives under a
    uuid-named folder.
    """
    found: list[str] = []
    for entry in bucket.list(prefix) or []:
        name = entry.get("name")
        if not name:
            continue
        path = f"{prefix}/{name}" if prefix else name
        if entry.get("id") is None:
            found.extend(_walk(bucket, path))
        else:
            found.append(path)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="Actually re-stamp. Without it, only reports.")
    args = ap.parse_args()

    client = get_service_client()
    checked = restamped = 0
    failures: list[str] = []

    for bucket_name in BUCKETS:
        bucket = client.storage.from_(bucket_name)
        try:
            paths = _walk(bucket)
        except Exception as exc:  # noqa: BLE001
            print(f"  {bucket_name}: could not list ({type(exc).__name__})")
            failures.append(bucket_name)
            continue

        print(f"\n{bucket_name}: {len(paths)} object(s)")
        for path in paths:
            checked += 1
            info = bucket.list("/".join(path.split("/")[:-1]) or None)
            meta = next((e.get("metadata") or {} for e in (info or [])
                         if e.get("name") == path.split("/")[-1]), {})
            current = meta.get("cacheControl")
            if current not in _STALE:
                print(f"  ok    {path}  (cache-control={current})")
                continue

            if not args.apply:
                print(f"  would re-stamp  {path}  (cache-control={current})")
                continue

            try:
                data = bucket.download(path)
                before = hashlib.sha256(data).hexdigest()
                mime = meta.get("mimetype") or "application/octet-stream"
                bucket.update(path, data, {
                    "content-type": mime,
                    "cache-control": PUBLIC_IMAGE_MAX_AGE,
                    "upsert": "true",
                })
                after = hashlib.sha256(bucket.download(path)).hexdigest()
            except Exception as exc:  # noqa: BLE001
                print(f"  FAIL  {path}: {type(exc).__name__}: {exc}")
                failures.append(path)
                continue

            if before != after:
                # Stop here. A changed object means the re-PUT is not
                # byte-preserving, and running it over the rest would spread
                # the damage instead of containing it.
                print(f"  CORRUPT  {path}: sha256 changed {before[:12]} -> "
                      f"{after[:12]}")
                print("  Stopping. No further objects touched.")
                return 2

            restamped += 1
            print(f"  done  {path}  ({len(data):,} B, sha256 unchanged)")

    print()
    verb = "re-stamped" if args.apply else "would re-stamp"
    print(f"{checked} object(s) checked, {restamped if args.apply else '-'} {verb}.")
    if failures:
        print(f"{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    if not args.apply:
        print("Dry run. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
