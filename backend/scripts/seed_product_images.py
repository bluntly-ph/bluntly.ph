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


def extract_og_image(html: str, base_url: str) -> str | None:
    parser = _MetaImageParser()
    parser.feed(html)
    found = parser.og or parser.twitter
    return urllib.parse.urljoin(base_url, found) if found else None


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
                product.image_fetched_at = datetime.now(UTC)
                db.commit()
                hits += 1
                print(f"  -> {product.image_url}")
            time.sleep(DELAY_S)

    print(f"\nresolved {hits}, unresolved {misses} of {hits + misses}")


if __name__ == "__main__":
    main()
