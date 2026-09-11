"""The showcase seed may not invent a marketplace URL (QA-006).

The first showcase seed wrote one affiliate URL per product by formatting the
product's own business id into a Shopee path — `shopee.ph/show_jisulife?af=bluntly`.
Those reached production and stayed there, so every "Buy it here" on the site
led to Shopee's "This shop failed to load". QA found it on 2026-09-08.

A fabricated affiliate URL is worse than no buy button in three separate ways:
the reader blames the platform for a broken link, the reviewer's commission path
is silently dead, and nothing in the system can tell the difference between a
placeholder and a link that has simply stopped working.

So the seed now refuses the shape. A product with no real link is seeded without
one, and its review is approved rather than monetized — no button at all.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from scripts.seed_showcase import _real_marketplace_url

# Real share links, as the marketplaces' own tools issue them.
SHOPEE = "https://s.shopee.ph/2gB11yLwBg"
LAZADA = "https://s.lazada.com.ph/s.ZSIo9U?c=t&t=p-i3NUbtB-sGfp3aj"


def test_a_real_share_link_passes_through_verbatim():
    """Verbatim matters: the query string IS the attribution. A link tidied up
    on the way into the database earns nobody anything."""
    assert _real_marketplace_url(SHOPEE, what="x") == SHOPEE
    assert _real_marketplace_url(LAZADA, what="x") == LAZADA


def test_no_link_is_none_rather_than_a_stand_in():
    assert _real_marketplace_url(None, what="x") is None
    assert _real_marketplace_url("", what="x") is None


@pytest.mark.parametrize("url", [
    "https://shopee.ph/show_jisulife?af=bluntly",   # the exact production defect
    "https://shopee.ph/show_macbook?af=bluntly",
    "https://lazada.com.ph/show_akko",
    "https://example.com/product/1",
])
def test_a_fabricated_url_is_refused(url):
    with pytest.raises(ValueError, match="placeholder"):
        _real_marketplace_url(url, what="show_thing shopee")


def test_the_refusal_names_the_product_and_the_url():
    """A seed that fails must say which entry to fix."""
    with pytest.raises(ValueError) as caught:
        _real_marketplace_url("https://shopee.ph/show_cerave?af=bluntly",
                              what="show_cerave shopee")
    message = str(caught.value)
    assert "show_cerave shopee" in message
    assert "QA-006" in message


def test_a_plain_http_url_is_refused():
    """Marketplace links are https; an http one is a copy-paste accident and
    would be downgraded or blocked in the browser anyway."""
    with pytest.raises(ValueError, match="https"):
        _real_marketplace_url("http://s.shopee.ph/2gB11yLwBg", what="x")


# The seeded set ---------------------------------------------------------------
#
# QA-006 was a data defect, so these assert the DATA, not just the helper. The
# affiliate links below are the owner's own, resolved to their listings in a real
# browser on 2026-09-10; the tests pin that what ships is what was resolved.

from app.models.enums import EarnEligibleStatus, Platform, ReferralLinkStatus  # noqa: E402
from scripts import seed_showcase as seed  # noqa: E402

NEW_PRODUCTS = [p for p in seed.PRODUCTS if p[5] or p[6]]


def test_every_seeded_link_is_a_real_marketplace_url():
    assert len(NEW_PRODUCTS) == 18
    for product in NEW_PRODUCTS:
        for url in (product[5], product[6]):
            if url is None:
                continue
            assert url.startswith("https://s.shopee.ph/") or url.startswith(
                "https://s.lazada.com.ph/"
            ), f"{product[1]}: {url}"
            # The guard must agree, and must hand the URL back untouched.
            assert seed._real_marketplace_url(url, what=product[1]) == url


def test_attribution_query_strings_are_intact():
    """Lazada's share links carry `?c=&t=` — that pair IS the attribution.

    A link "cleaned up" on the way into the database still reaches the right
    product and still earns nothing, which is the kind of breakage nobody
    notices until a payout cycle comes up short.
    """
    lazada = [p[6] for p in NEW_PRODUCTS if p[6]]
    assert len(lazada) == 8
    for url in lazada:
        assert "?c=" in url and "&t=" in url, url


def test_each_product_carries_exactly_one_marketplace_link():
    """The supplied set contains no cross-marketplace pairs.

    Resolving all twenty links found no Shopee listing selling the same product
    as any Lazada one, so no product here is dual-listed. This test exists so
    that stops being an assumption: if a future pair IS added, it fails and the
    referral-platform choice gets looked at again rather than silently
    defaulting.
    """
    for product in NEW_PRODUCTS:
        assert bool(product[5]) != bool(product[6]), f"{product[1]} has both or neither"


def test_the_referral_platform_follows_the_link():
    """Eight of these are Lazada-only. Hardcoding Shopee would have labelled
    them as Shopee referrals and left them unmonetized."""
    split = {}
    for product in seed.PRODUCTS:
        platform, url = seed._affiliate_for(product)
        key = platform.value if platform else "none"
        split[key] = split.get(key, 0) + 1
        if url:
            assert url == (product[5] or product[6])
            expected = Platform.shopee if product[5] else Platform.lazada
            assert platform is expected
    assert split == {"shopee": 10, "lazada": 8, "none": 6}


def test_the_six_legacy_products_carry_no_invented_link():
    """The original showcase products had fabricated URLs. Until real ones
    exist they carry none, and their reviews lose the buy button rather than
    keep a broken one."""
    legacy = [p for p in seed.PRODUCTS if not p[5] and not p[6]]
    assert len(legacy) == 6
    for product in legacy:
        assert seed._affiliate_for(product) == (None, None)


# Fixtures must never claim to be real purchases -------------------------------

def test_only_the_six_original_reviews_are_verified():
    assert len(seed.LEGACY_VERIFIED) == 6
    seeded_ids = {r[1] for r in seed.REVIEWS}
    assert seed.LEGACY_VERIFIED <= seeded_ids
    new_ids = seeded_ids - seed.LEGACY_VERIFIED
    assert len(new_ids) == 18
    # Nothing added for QA-006 presents itself as a confirmed purchase.
    assert not (new_ids & seed.LEGACY_VERIFIED)


def test_no_showcase_review_claims_a_price_paid():
    """`price_paid` is what the reviewer says they paid. A fixture asserting a
    figure it cannot have paid is a fabricated purchase detail, so the new set
    leaves it unset."""
    for review in seed.REVIEWS:
        if review[1] in seed.LEGACY_VERIFIED:
            continue
        assert review[13] is None, f"{review[1]} carries a price_paid"


def test_every_showcase_id_stays_inside_the_removable_namespace():
    for product in seed.PRODUCTS:
        assert product[1].startswith("show_")
    for review in seed.REVIEWS:
        assert review[1].startswith("rev_show_")
    # The docstring's cleanup deletes users by `usr_show_%`, and the seeder
    # builds that id as f"usr_show_{username}" — so the username is what has to
    # survive as a suffix. The old assertion here checked nothing of the sort.
    for author in seed.AUTHORS:
        assert f"usr_show_{author[1]}".startswith("usr_show_")
        assert author[1] and " " not in author[1]


def test_the_documented_cleanup_still_matches_what_is_seeded():
    """The module docstring carries the removal SQL. If the namespaces drift
    apart, the documented cleanup silently stops removing everything."""
    doc = seed.__doc__ or ""
    for fragment in ("rev_show_%", "show_%", "usr_show_%"):
        assert fragment in doc, fragment
    assert all(p[1].startswith("show_") for p in seed.PRODUCTS)
    assert all(r[1].startswith("rev_show_") for r in seed.REVIEWS)


def test_reviews_point_at_products_and_authors_that_exist():
    for review in seed.REVIEWS:
        assert 0 <= review[2] < len(seed.PRODUCTS), review[1]
        assert 0 <= review[3] < len(seed.AUTHORS), review[1]


def test_ids_are_unique_across_the_whole_set():
    for label, values in (
        ("product uuid", [p[0] for p in seed.PRODUCTS]),
        ("product_id", [p[1] for p in seed.PRODUCTS]),
        ("review uuid", [r[0] for r in seed.REVIEWS]),
        ("review_id", [r[1] for r in seed.REVIEWS]),
        ("author uuid", [a[0] for a in seed.AUTHORS]),
    ):
        assert len(values) == len(set(values)), f"duplicate {label}"


# The repair path --------------------------------------------------------------

class _FakeQuery:
    """A query that actually applies `filter_by`.

    The first version of this fake discarded its filter arguments, which made
    the idempotence test vacuous: it passed whether or not the production code
    filtered on `status`, and the missing filter is exactly what would cause
    revoked links to accumulate. It filters for real now.
    """

    def __init__(self, rows):
        self._rows = list(rows)

    def filter_by(self, **criteria):
        return _FakeQuery([
            row for row in self._rows
            if all(getattr(row, key, None) == value for key, value in criteria.items())
        ])

    def first(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _FakeDb:
    """Enough Session surface for `_repair_review_link`, and a record of what
    it was asked to add — so "touched nothing" is provable."""

    def __init__(self, link=None, links=None):
        self.rows = list(links) if links is not None else ([link] if link else [])
        self.added = []

    def query(self, *_):
        return _FakeQuery(self.rows)

    def add(self, obj):
        self.added.append(obj)


class _FakeReview:
    def __init__(self, review_id, status=EarnEligibleStatus.monetized, link="x",
                 published=True, removed=False, stars=4, photo=None):
        self.id = "rid"
        self.review_id = review_id
        self.affiliate_link = link
        self.earn_eligible_status = status
        self.current_version = 1
        self.published_at = "2026-09-01T00:00:00Z" if published else None
        self.is_removed = removed
        self.star_rating = stars
        self.photo_url = photo


class _FakeLink:
    def __init__(self, url, status=ReferralLinkStatus.active, platform=Platform.shopee,
                 review_id="rid"):
        # `review_id` matters: the production lookup filters on it, and the
        # fake query now honours filter_by. Without it every link is filtered
        # out and the repair looks like it has none to work with.
        self.review_id = review_id
        self.url = url
        self.status = status
        self.platform = platform
        self.revoked_by = None
        self.revoked_at = None
        self.revoke_reason = None


def test_repair_ignores_reviews_outside_the_showcase_namespace():
    """The one thing this must never do is rewrite a link a moderator attached
    by hand."""
    real = _FakeReview("rev_a1b2c3d4e5", link="https://s.shopee.ph/realLink")
    db = _FakeDb()
    seed._repair_review_link(db, real, Platform.shopee, "https://s.shopee.ph/other", "aid")
    assert real.affiliate_link == "https://s.shopee.ph/realLink"
    assert real.earn_eligible_status == EarnEligibleStatus.monetized
    assert db.added == []


def test_repair_attaches_a_real_link_to_a_showcase_review():
    review = _FakeReview("rev_show_iphone17", status=EarnEligibleStatus.approved, link=None)
    db = _FakeDb()
    seed._repair_review_link(db, review, Platform.lazada, "https://s.lazada.com.ph/s.X", "aid")
    assert review.affiliate_link == "https://s.lazada.com.ph/s.X"
    assert review.earn_eligible_status == EarnEligibleStatus.monetized
    assert len(db.added) == 1
    assert db.added[0].platform is Platform.lazada


def test_repair_retracts_the_button_when_there_is_no_real_link():
    """A showcase review whose product has no real link must lose its buy
    button, not keep pointing at a page that fails to load."""
    link = _FakeLink("https://shopee.ph/show_jisulife?af=bluntly")
    review = _FakeReview("rev_show_jisulife", photo="https://example.com/showcase.jpg")
    db = _FakeDb(link=link)

    seed._repair_review_link(db, review, None, None, "aid")

    assert link.status is ReferralLinkStatus.revoked
    assert review.affiliate_link is None
    assert review.earn_eligible_status == EarnEligibleStatus.approved
    assert db.added == []
    # The fake photo goes with it: the row claimed a photo that renders as
    # nothing, because `usablePhoto` filters example.com.
    assert review.photo_url is None


def test_a_retraction_is_audited_like_a_real_revoke():
    """`referral_service.revoke_link` records who, when and why. A seeded
    retraction that skips them leaves the admin link history showing a link
    revoked by nobody, for no reason."""
    link = _FakeLink("https://shopee.ph/show_akko?af=bluntly")
    review = _FakeReview("rev_show_akko")
    db = _FakeDb(link=link)

    seed._repair_review_link(db, review, None, None, "author-uuid")

    assert link.revoked_by == "author-uuid"
    assert link.revoked_at is not None
    assert "QA-006" in (link.revoke_reason or "")


def test_a_low_star_retraction_routes_to_the_honesty_fund():
    """Two stars and below never sit in `approved` — they belong to the fund,
    which is the same rule the insert path applies."""
    review = _FakeReview("rev_show_airism", stars=2)
    db = _FakeDb(link=_FakeLink("https://shopee.ph/show_airism?af=bluntly"))

    seed._repair_review_link(db, review, None, None, "aid")

    assert review.earn_eligible_status == EarnEligibleStatus.honesty_fund


def test_repair_will_not_re_monetize_an_unpublished_review():
    """`unpublish` clears published_at AND moves the status back to pending so
    the row stays reachable from the moderator queue. Re-monetizing it here
    would strand it — invisible to readers, absent from the queue — which is
    the state invariant #8 exists to catch, and which sat in production for
    eleven days once."""
    review = _FakeReview("rev_show_iphone17", status=EarnEligibleStatus.pending,
                         link=None, published=False)
    link = _FakeLink("https://s.shopee.ph/old")
    db = _FakeDb(link=link)

    seed._repair_review_link(db, review, Platform.shopee, "https://s.shopee.ph/2gB11yLwBg", "aid")

    assert review.earn_eligible_status == EarnEligibleStatus.pending
    assert review.published_at is None
    assert db.added == []
    # Repointing the existing link is still correct — it just stays inactive
    # until a moderator republishes.
    assert link.url == "https://s.shopee.ph/2gB11yLwBg"


def test_repair_will_not_resurrect_a_deliberately_revoked_link():
    """Every link revoked means somebody took that button down. Adding a fresh
    active one would silently undo the decision."""
    revoked = _FakeLink("https://s.shopee.ph/old", status=ReferralLinkStatus.revoked)
    review = _FakeReview("rev_show_iphone17", status=EarnEligibleStatus.approved, link=None)
    db = _FakeDb(links=[revoked])

    seed._repair_review_link(db, review, Platform.shopee, "https://s.shopee.ph/new", "aid")

    assert db.added == [], "a revoked link must not be replaced with a new active one"
    assert review.earn_eligible_status == EarnEligibleStatus.approved


def test_repair_is_idempotent_for_an_already_correct_row():
    link = _FakeLink("https://s.shopee.ph/2gB11yLwBg")
    review = _FakeReview("rev_show_uratex", link="https://s.shopee.ph/2gB11yLwBg")
    db = _FakeDb(link=link)

    seed._repair_review_link(db, review, Platform.shopee, "https://s.shopee.ph/2gB11yLwBg", "aid")

    assert link.url == "https://s.shopee.ph/2gB11yLwBg"
    assert review.affiliate_link == "https://s.shopee.ph/2gB11yLwBg"
    assert db.added == [], "a second run must not add a duplicate referral link"


# The invariant this fixture set deliberately bends ----------------------------

def test_the_fixture_set_matches_the_amended_invariant():
    """`check_invariants` #9 says monetized implies verified, and now exempts
    the `rev_show_` namespace. This pins both halves of that bargain: the
    fixtures really are the only rows relying on the exemption, and none of
    them claims verification.
    """
    from scripts.check_invariants import CHECKS

    by_name = {name: sql for name, sql, _ in CHECKS}
    assert "rev_show_%" in by_name["monetized but unverified"], (
        "invariant #9 no longer exempts the showcase namespace, so seeding "
        "these fixtures would fail release-acceptance step 11"
    )
    honesty = by_name["showcase fixture claiming a verified purchase"]
    for legacy in seed.LEGACY_VERIFIED:
        assert legacy in honesty, f"{legacy} is not exempted from the honesty check"


def test_sub_id_visibility_is_computed_not_assumed():
    """A false `sub_id_in_url` means the monthly marketplace report comes back
    unattributable, so it is derived rather than asserted."""
    assert seed._sub_id_visible("https://s.shopee.ph/2gB11yLwBg", "rev_show_uratex") is False
    assert seed._sub_id_visible("https://x.test/p?sub_id1=rev_show_uratex",
                                "rev_show_uratex") is True
    assert seed._sub_id_visible("https://x.test/p", None) is False


def test_the_guard_rejects_a_host_the_redirect_would_refuse():
    """Shape alone is not enough: the host must be on the same allowlist
    `referral_service.validate_affiliate_url` uses, or the redirect refuses it
    and QA-006 comes back wearing a different URL."""
    with pytest.raises(ValueError, match="affiliate domain"):
        seed._real_marketplace_url("https://tiktokshop.ph/product/123", what="x")
    # And the real ones still pass.
    assert seed._real_marketplace_url(SHOPEE, what="x") == SHOPEE
    assert seed._real_marketplace_url(LAZADA, what="x") == LAZADA


def test_repair_engagement_derives_the_total_from_the_vote_rows():
    """QA-011, without a database.

    The seed wrote helpful_votes straight onto the row — 97, 88, 81 — with no
    `review_votes` behind them, and `vote_service` derives the count from those
    rows alone. The first genuine upvote recomputed the aggregate from the real
    data and "97" became "1". QA read that as the counter resetting; it was the
    fabrication collapsing.

    `_repair_engagement` now delegates to the same service the vote path uses,
    so this drives it with a session that reports the votes and checks what
    lands on the row — rather than grepping the source, which would pass on a
    comment and break on a rename.
    """
    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def __iter__(self):
            return iter(self._rows)

    class _Db:
        def __init__(self, rows):
            self.rows = rows

        def execute(self, *_a, **_k):
            return _Result(self.rows)

    class _Row:
        def __init__(self, review_id):
            self.id = "rid"
            self.review_id = review_id
            self.helpful_votes = 97
            self.unhelpful_votes = 2
            self.wilson_score = Decimal("0.96")

    # No vote rows behind it: the honest total is zero, and 0 -> 1 on the next
    # real upvote is then exactly what one vote means.
    row = _Row("rev_show_iphone17")
    seed._repair_engagement(_Db([]), row)
    assert row.helpful_votes == 0
    assert row.unhelpful_votes == 0
    assert Decimal(row.wilson_score) == Decimal("0")

    # Outside the namespace nothing is touched, whatever the votes say.
    real = _Row("rev_a1b2c3d4e5")
    seed._repair_engagement(_Db([]), real)
    assert real.helpful_votes == 97
