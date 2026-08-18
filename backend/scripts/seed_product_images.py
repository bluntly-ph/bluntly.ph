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
import pathlib
import socket
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import UTC, datetime
from functools import lru_cache
from html.parser import HTMLParser

from app.db.session import SessionLocal
from app.models.enums import ImageSource
from app.models.product import Product
from app.services.storage import upload_product_image

USER_AGENT = "bluntly.ph/1.0 (+https://www.bluntly.ph)"
MAX_HTML_BYTES = 512 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_ROBOTS_BYTES = 64 * 1024
MAX_REDIRECTS = 3
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


def _https_upgrade(url: str) -> str:
    """http:// -> https:// on the same host.

    Plenty of storefronts still emit an http og:image even when the page itself
    is https and the asset is served fine over both — Shopify does it, which is
    why jisulife.com produced a perfectly good tag that we then refused to
    fetch. `is_fetchable` requires https, so without this the guard silently
    rejects a valid image. Upgrading is strictly safer than the alternative of
    relaxing the scheme check, and if https genuinely is not available the
    fetch fails and we fall through to the moderator path as before.
    """
    return "https://" + url[len("http://"):] if url.startswith("http://") else url


def extract_og_image(html: str, base_url: str) -> str | None:
    parser = _MetaImageParser()
    parser.feed(html)
    found = parser.og or parser.twitter
    return _https_upgrade(urllib.parse.urljoin(base_url, found)) if found else None


def is_fetchable(url: str) -> bool:
    """https, resolvable, and not pointing anywhere inside our network."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    return is_public_host(parsed.hostname)


class _ValidatingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-check the host on every redirect hop.

    Without this the SSRF guard is decorative: a listing URL on a perfectly
    legitimate public host can 302 to 169.254.169.254 and urllib will follow it
    without consulting us again. Refusing here surfaces as an HTTPError, which
    the caller already treats as "no image".
    """

    max_redirections = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        if not is_fetchable(newurl):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_ValidatingRedirectHandler)


def _fetch(url: str, max_bytes: int) -> bytes | None:
    """Raw guarded GET. Does NOT consult robots.txt — see `_get` for that."""
    if not is_fetchable(url):
        return None
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _opener.open(req, timeout=TIMEOUT_S) as resp:
            return resp.read(max_bytes + 1)[:max_bytes]
    except Exception:
        return None


@lru_cache(maxsize=64)
def _robots_for(origin: str) -> urllib.robotparser.RobotFileParser:
    """Parsed robots.txt for an origin. Fetched at most once per run."""
    parser = urllib.robotparser.RobotFileParser()
    body = _fetch(f"{origin}/robots.txt", MAX_ROBOTS_BYTES)
    # An absent or unreachable robots.txt is not a disallow — that is the
    # convention every well-behaved crawler follows. We use our own guarded
    # fetch rather than RobotFileParser.read(), which has no timeout.
    parser.parse(body.decode("utf-8", "replace").splitlines() if body else [])
    return parser


def robots_allows(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if not parsed.hostname:
        return False
    return _robots_for(f"{parsed.scheme}://{parsed.netloc}").can_fetch(USER_AGENT, url)


def _get(url: str, max_bytes: int) -> bytes | None:
    """Guarded GET that also honours robots.txt."""
    if not is_fetchable(url) or not robots_allows(url):
        return None
    return _fetch(url, max_bytes)


def resolve_image(url: str) -> bytes | None:
    """Listing URL -> image bytes, or None. Never raises."""
    page = _get(url, MAX_HTML_BYTES)
    if page is None:
        return None
    image_url = extract_og_image(page.decode("utf-8", "replace"), url)
    if image_url is None:
        return None
    return _get(image_url, MAX_IMAGE_BYTES)


def _load_map(path: str) -> list[tuple[str, str]]:
    """`canonical_name<TAB>page_url` pairs from a checked-in TSV.

    The alternative was to write these URLs into `products.source_url`, and
    that would have been a lie: source_url means "the marketplace listing this
    product was submitted from" and feeds canonicalization (models/product.py
    §3.1). A brand's own product page is a fine place to read an og:image from
    and a wrong answer to "where did this listing come from". Keeping the two
    apart costs one small file and leaves both fields true.
    """
    pairs: list[tuple[str, str]] = []
    for raw in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, _, url = line.partition("	")
        if url.strip():
            pairs.append((name.strip(), url.strip()))
    return pairs


def _apply(db, product: Product, url: str, dry_run: bool) -> bool:
    """Resolve one product's image and persist it. True if an image landed."""
    print(f"[fetch] {product.canonical_name or product.id} {url}")
    data = resolve_image(url)
    if data is None:
        print("  -> no usable og:image (moderator will supply)")
        return False
    if dry_run:
        print(f"  -> would upload {len(data)} bytes")
        return True
    product.image_url = upload_product_image(product.id, data)
    product.image_source = ImageSource.seeded
    product.image_fetched_at = datetime.now(UTC)
    db.commit()
    print(f"  -> {product.image_url}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--from-file",
        metavar="TSV",
        help="canonical_name<TAB>page_url map to seed from instead of source_url",
    )
    args = ap.parse_args()

    hits = misses = 0
    with SessionLocal() as db:
        if args.from_file:
            for name, url in _load_map(args.from_file):
                product = (db.query(Product)
                             .filter(Product.canonical_name == name).one_or_none())
                if product is None:
                    print(f"[skip ] no product named {name!r}")
                    misses += 1
                    continue
                if product.image_url is not None:
                    print(f"[skip ] {name} already has an image")
                    continue
                hits, misses = ((hits + 1, misses) if _apply(db, product, url, args.dry_run)
                                else (hits, misses + 1))
                time.sleep(DELAY_S)
        else:
            products = (db.query(Product)
                          .filter(Product.image_url.is_(None),
                                  Product.source_url.isnot(None))
                          .limit(args.limit).all())
            for product in products:
                hits, misses = ((hits + 1, misses)
                                if _apply(db, product, product.source_url, args.dry_run)
                                else (hits, misses + 1))
                time.sleep(DELAY_S)

    print(f"\nresolved {hits}, unresolved {misses} of {hits + misses}")



if __name__ == "__main__":
    main()
