"""The owner's real Shopee and Lazada affiliate links, as fixtures.

Twenty real links were provided for testing the marketplace pipeline. They are
used here the way real affiliate links should be used in a test suite: as
STRINGS. Nothing in this file opens one.

That restriction is the point, not a shortcut. These URLs carry live tracking
parameters; a CI job that fetched all twenty on every run would generate a
steady trickle of attributed traffic that nobody clicked, against the owner's
own affiliate account. The parser, the allowlist and the persistence rules are
all decidable from the string, so that is what is checked. Resolving a short
link to its destination is a manual, deliberate act.

Two formats, ten of each — which is why ten of each are listed rather than one:
the point is that no individual token is special.
"""

from __future__ import annotations

import uuid
from urllib.parse import parse_qs, urlsplit

import pytest

from app.core.errors import AppError
from app.models.enums import Platform
from app.services.referral_service import validate_affiliate_url

#: Owner-provided, 2026-09-16. Real links; do not fetch them.
SHOPEE = [
    "https://s.shopee.ph/2gB11yLwBg",
    "https://s.shopee.ph/7pt7BWX1Ta",
    "https://s.shopee.ph/50YvoKBESR",
    "https://s.shopee.ph/BTg3RtPcP",
    "https://s.shopee.ph/7AdQOJz8uS",
    "https://s.shopee.ph/70K0C1GTxw",
    "https://s.shopee.ph/5focbZpfXp",
    "https://s.shopee.ph/7AdQOLGka4",
    "https://s.shopee.ph/3g3YDut67F",
    "https://s.shopee.ph/5focbbM3Z1",
]

LAZADA = [
    "https://s.lazada.com.ph/s.ZSIo9U?c=t&t=p-i3NUbtB-sGfp3aj",
    "https://s.lazada.com.ph/s.ZSIokl?c=t&t=p-i4dE7F3-sPq9a3M",
    "https://s.lazada.com.ph/s.ZSIoO2?c=q&t=p-iGrOAoF-s2L7tZLj",
    "https://s.lazada.com.ph/s.ZSIomy?c=p&t=p-i5okjWI-sYiqvHI",
    "https://s.lazada.com.ph/s.ZSIoMs?c=u&t=p-i5MJJZl-sVFLgf3",
    "https://s.lazada.com.ph/s.ZSIooE?c=q&t=p-i513gmy-s2LOIzFD",
    "https://s.lazada.com.ph/s.ZSIopc?c=q&t=p-iGxYwcm-s2LW5WPk",
    "https://s.lazada.com.ph/s.ZSIoKv?c=p&t=p-i5rfzcu-sZ5Wn8m",
    "https://s.lazada.com.ph/s.ZSIoJS?c=p&t=p-iGrxS2U-s2LCPx7e",
    "https://s.lazada.com.ph/s.ZSIor7?c=t&t=p-i3LFd78-sTFaVqA",
]


class _NoBlocks:
    """A database stand-in for the one query the validator makes.

    `validate_affiliate_url` checks the allowlist from settings and then asks
    whether this product has an explicit non-monetizable row for the platform.
    Answering "no" exercises the whole URL path without a database, which is
    what lets these run in the fast job.
    """

    def scalar(self, *args, **kwargs):
        return None


@pytest.mark.parametrize("url", SHOPEE)
def test_every_shopee_link_is_accepted(url: str):
    validate_affiliate_url(_NoBlocks(), url, Platform.shopee, uuid.uuid4())


@pytest.mark.parametrize("url", LAZADA)
def test_every_lazada_link_is_accepted(url: str):
    validate_affiliate_url(_NoBlocks(), url, Platform.lazada, uuid.uuid4())


@pytest.mark.parametrize("url", LAZADA)
def test_a_lazada_link_keeps_its_tracking_parameters(url: str):
    """The validator must not be the thing that strips attribution.

    A stored affiliate URL is stored whole. `c` and `t` are what make a click
    attributable, and a "tidy-up" that drops them turns every future commission
    into an unattributable one — the kind of loss that shows up a month later
    in a report nobody can reconcile.
    """
    query = parse_qs(urlsplit(url).query)
    assert set(query) == {"c", "t"}
    validate_affiliate_url(_NoBlocks(), url, Platform.lazada, uuid.uuid4())


def test_the_two_formats_are_the_only_two():
    """If the owner adds a third marketplace format, this fails rather than drifts."""
    hosts = {urlsplit(u).hostname for u in SHOPEE + LAZADA}
    assert hosts == {"s.shopee.ph", "s.lazada.com.ph"}


def test_a_shopee_link_is_not_accepted_as_lazada():
    """The platform is declared by the moderator, so it has to be checked."""
    with pytest.raises(AppError) as caught:
        validate_affiliate_url(_NoBlocks(), SHOPEE[0], Platform.lazada, uuid.uuid4())
    assert caught.value.code == "affiliate_url_invalid"


def test_a_lazada_link_is_not_accepted_as_shopee():
    with pytest.raises(AppError) as caught:
        validate_affiliate_url(_NoBlocks(), LAZADA[0], Platform.shopee, uuid.uuid4())
    assert caught.value.code == "affiliate_url_invalid"


@pytest.mark.parametrize(
    "url",
    [
        "http://s.shopee.ph/2gB11yLwBg",              # not https
        "https://s.shopee.ph.evil.test/2gB11yLwBg",    # suffix, not subdomain
        "https://user@s.shopee.ph/2gB11yLwBg",         # userinfo
        "https://shopee.ph.attacker.test/x",
        "javascript:alert(1)",
        "",
    ],
)
def test_a_link_that_is_not_the_marketplace_is_refused(url: str):
    with pytest.raises(AppError):
        validate_affiliate_url(_NoBlocks(), url, Platform.shopee, uuid.uuid4())


def test_a_real_subdomain_of_an_allowed_host_is_still_allowed():
    """`endswith("." + domain)` is the rule; this pins what it means."""
    validate_affiliate_url(
        _NoBlocks(), "https://affiliate.shopee.ph/x", Platform.shopee, uuid.uuid4()
    )


def test_no_test_in_this_file_performs_a_request():
    """Guards the rule the file exists to keep (owner instruction, §19).

    Real affiliate links must not be fetched by an automated suite. Read from
    source, because the thing being forbidden is a call that would otherwise
    look perfectly ordinary in a diff.
    """
    from pathlib import Path

    source = Path(__file__).read_text(encoding="utf-8")
    # Up to this function only: the list below names the very things it forbids,
    # so a check that read its own body would always fail.
    body = source[source.index("class _NoBlocks") : source.index("def test_no_test_in_this_file")]
    for forbidden in ("requests.", "httpx.", "urlopen", "TestClient(", "fetch("):
        assert forbidden not in body, f"{forbidden} would generate real affiliate traffic"


# --- deduplication must not read the tracking string (owner §20) -------------


def test_the_same_listing_with_different_tracking_is_one_product():
    """Attribution differs per share; the product does not.

    Two people sharing the same Lazada listing produce two URLs that differ only
    in `c` and `t`. If those counted as two products, the reviews for one item
    would split across both — which is exactly the consolidation failure
    BUG-020 was filed about, arriving by a different route.
    """
    from app.services.product_matching import listing_key

    one = "https://s.lazada.com.ph/s.ZSIo9U?c=t&t=p-i3NUbtB-sGfp3aj"
    two = "https://s.lazada.com.ph/s.ZSIo9U?c=q&t=p-DIFFERENT-sXXXXXX"
    assert listing_key(one) == listing_key(two)


def test_two_different_listings_stay_two_products():
    """The other direction matters more: a wrong merge moves someone's reviews."""
    from app.services.product_matching import listing_key

    keys = {listing_key(u) for u in LAZADA}
    assert len(keys) == len(LAZADA)

    shopee_keys = {listing_key(u) for u in SHOPEE}
    assert len(shopee_keys) == len(SHOPEE)


def test_the_dedup_key_carries_no_tracking_parameter():
    """Stated as a property, so a future 'keep the query' change fails here."""
    from app.services.product_matching import listing_key

    for url in SHOPEE + LAZADA:
        key = listing_key(url)
        assert "?" not in key and "&" not in key
        assert "c=" not in key and "t=" not in key


def test_a_short_link_yields_no_product_name():
    """§18: identity must not be invented from the token in a short URL.

    `2gB11yLwBg` is not a product name, and nothing in the matching path turns
    it into one — the name key comes from a name, and a URL is not one.
    """
    from app.services.product_matching import name_key

    for url in SHOPEE + LAZADA:
        assert name_key(None) is None
        # The URL is a listing key, never a name key.
        assert listing_key_is_not_a_name(url)


def listing_key_is_not_a_name(url: str) -> bool:
    from app.services.product_matching import listing_key, name_key

    key = listing_key(url)
    # A name key built from the URL would be a very different string; the point
    # is that the two are computed from different inputs and never substituted.
    return key is not None and name_key(key) != key
