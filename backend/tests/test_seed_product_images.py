import urllib.robotparser

import pytest

from scripts.seed_product_images import (
    USER_AGENT,
    _ValidatingRedirectHandler,
    extract_og_image,
    is_fetchable,
    is_public_host,
)


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


# --- Redirect validation -----------------------------------------------------
# The initial-host check is worthless on its own: urllib follows redirects by
# default, so a listing on a legitimate host can bounce to a metadata endpoint.


@pytest.mark.parametrize("url", [
    "https://169.254.169.254/latest/meta-data/",
    "https://127.0.0.1/admin",
    "https://10.0.0.5/internal",
    "http://shopee.ph/p/1",          # plain http is refused outright
    "ftp://shopee.ph/p/1",
])
def test_is_fetchable_refuses_unsafe_targets(url):
    assert is_fetchable(url) is False


def test_is_fetchable_accepts_public_https():
    assert is_fetchable("https://shopee.ph/product/1") is True


def test_redirect_handler_refuses_hop_into_private_range():
    """A 302 toward the cloud metadata endpoint must not be followed."""
    handler = _ValidatingRedirectHandler()
    result = handler.redirect_request(
        req=None, fp=None, code=302, msg="Found", headers={},
        newurl="https://169.254.169.254/latest/meta-data/",
    )
    assert result is None


def test_redirect_handler_caps_hops():
    assert _ValidatingRedirectHandler.max_redirections == 3


# --- robots.txt --------------------------------------------------------------


def _robots(text: str) -> urllib.robotparser.RobotFileParser:
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(text.splitlines())
    return parser


def test_robots_disallow_is_honoured():
    parser = _robots("User-agent: *\nDisallow: /product/")
    assert parser.can_fetch(USER_AGENT, "https://shop.test/product/1") is False


def test_robots_allow_is_honoured():
    parser = _robots("User-agent: *\nDisallow: /admin/")
    assert parser.can_fetch(USER_AGENT, "https://shop.test/product/1") is True


def test_absent_robots_is_not_a_disallow():
    """Convention: an empty or missing robots.txt permits crawling."""
    assert _robots("").can_fetch(USER_AGENT, "https://shop.test/product/1") is True
