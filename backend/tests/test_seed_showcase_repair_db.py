"""The showcase repair path, against a real database.

The pure tests in `test_seed_showcase_links.py` drive `_repair_review_link` and
`_upsert_product` through hand-built fakes. That is enough to pin the branching,
and not enough to pin the SQL: a fake cannot tell you that `filter_by` matched
the rows you meant, that `uq_product_platform` tolerates what the upsert does to
it, or that a real `ReferralLink` row accepts the audit fields being set.

These do that. They only run where a real PostgreSQL exists — CI's isolated
database job — because there is none on the development machine this was written
on, which is exactly why the gap was worth closing: the repair path mutates
production rows and had no integration coverage anywhere.

Everything here is rolled back by the `db` fixture.
"""

from __future__ import annotations

import uuid

from app.models.enums import (
    EarnEligibleStatus,
    Platform,
    ProductStatus,
    ReferralLinkStatus,
    Verdict,
    VerificationStatus,
)
from app.models.product import Product, ProductPlatform
from app.models.review import ReferralLink, Review
from scripts import seed_showcase as seed
from tests.conftest import make_user, requires_db

FAKE = "https://shopee.ph/show_fixture?af=bluntly"
REAL = "https://s.shopee.ph/2gB11yLwBg"


def _showcase_review(db, review_id: str, *, author, product, link_url=FAKE,
                     status=EarnEligibleStatus.monetized, stars=4):
    review = Review(
        review_id=review_id, product_id=product.id, author_id=author.id,
        title=f"Fixture {review_id}", discussion="Body text for a repair fixture.",
        verdict=Verdict.it_depends, star_rating=stars, is_removed=False,
        published_at=seed.NOW, earn_eligible_status=status, current_version=1,
        affiliate_link=link_url, verification_status=VerificationStatus.verified,
        photo_url="https://example.com/showcase.jpg",
    )
    db.add(review)
    db.flush()
    if link_url:
        db.add(ReferralLink(
            review_id=review.id, platform=Platform.shopee, url=link_url,
            sub_id=review_id, sub_id_in_url=False,
            status=ReferralLinkStatus.active, review_version=1, created_by=author.id,
        ))
        db.flush()
    return review


def _product(db, product_id: str):
    product = Product(
        product_id=product_id, canonical_name=f"Fixture {product_id}",
        status=ProductStatus.canonicalized,
    )
    db.add(product)
    db.flush()
    return product


def _active_link(db, review):
    return (db.query(ReferralLink)
            .filter_by(review_id=review.id, status=ReferralLinkStatus.active)
            .first())


@requires_db
def test_a_fabricated_link_is_retracted_with_a_full_audit_trail(db):
    """The production case: four reviews carry an invented URL right now."""
    marker = uuid.uuid4().hex[:8]
    author = make_user(db)
    product = _product(db, f"show_repair_{marker}")
    review = _showcase_review(db, f"rev_show_repair_{marker}",
                              author=author, product=product)
    db.flush()

    seed._repair_review_link(db, review, None, None, author.id)
    db.flush()

    assert review.affiliate_link is None
    assert review.earn_eligible_status == EarnEligibleStatus.approved
    assert review.photo_url is None, "the example.com photo goes with it"
    assert _active_link(db, review) is None

    revoked = db.query(ReferralLink).filter_by(review_id=review.id).one()
    assert revoked.status is ReferralLinkStatus.revoked
    assert revoked.revoked_by == author.id
    assert revoked.revoked_at is not None
    assert "QA-006" in (revoked.revoke_reason or "")


@requires_db
def test_a_real_link_replaces_the_fabricated_one_in_place(db):
    """One active link before, one after — not two."""
    marker = uuid.uuid4().hex[:8]
    author = make_user(db)
    product = _product(db, f"show_repair_{marker}")
    review = _showcase_review(db, f"rev_show_repair_{marker}",
                              author=author, product=product)
    db.flush()

    seed._repair_review_link(db, review, Platform.shopee, REAL, author.id)
    db.flush()

    assert review.affiliate_link == REAL
    assert review.earn_eligible_status == EarnEligibleStatus.monetized
    assert db.query(ReferralLink).filter_by(review_id=review.id).count() == 1
    assert _active_link(db, review).url == REAL


@requires_db
def test_repairing_twice_changes_nothing_the_second_time(db):
    marker = uuid.uuid4().hex[:8]
    author = make_user(db)
    product = _product(db, f"show_repair_{marker}")
    review = _showcase_review(db, f"rev_show_repair_{marker}",
                              author=author, product=product)
    db.flush()

    for _ in range(2):
        seed._repair_review_link(db, review, Platform.shopee, REAL, author.id)
        db.flush()

    links = db.query(ReferralLink).filter_by(review_id=review.id).all()
    assert len(links) == 1, "a re-run must not accumulate referral links"
    assert links[0].url == REAL
    assert links[0].status is ReferralLinkStatus.active


@requires_db
def test_a_real_review_is_never_touched(db):
    """The whole safety argument, against real SQL rather than a fake."""
    marker = uuid.uuid4().hex[:8]
    author = make_user(db)
    product = _product(db, f"prd_real_{marker}")
    # A `rev_` id, as `review_service` mints for genuine reviews.
    review = _showcase_review(db, f"rev_{uuid.uuid4().hex[:10]}",
                              author=author, product=product,
                              link_url="https://s.shopee.ph/moderatorChoice")
    db.flush()

    seed._repair_review_link(db, review, Platform.shopee, REAL, author.id)
    db.flush()

    assert review.affiliate_link == "https://s.shopee.ph/moderatorChoice"
    assert review.earn_eligible_status == EarnEligibleStatus.monetized
    assert _active_link(db, review).url == "https://s.shopee.ph/moderatorChoice"


@requires_db
def test_an_unpublished_showcase_review_keeps_its_lifecycle_state(db):
    """Re-monetizing an unpublished row strands it: invisible to readers and
    absent from the queue, which is what invariant #8 catches and what sat in
    production for eleven days once."""
    marker = uuid.uuid4().hex[:8]
    author = make_user(db)
    product = _product(db, f"show_repair_{marker}")
    review = _showcase_review(db, f"rev_show_repair_{marker}",
                              author=author, product=product,
                              status=EarnEligibleStatus.pending)
    review.published_at = None
    db.flush()

    seed._repair_review_link(db, review, Platform.shopee, REAL, author.id)
    db.flush()

    assert review.earn_eligible_status == EarnEligibleStatus.pending
    assert review.published_at is None
    # The link is still repointed — it just stays inactive until republished.
    assert _active_link(db, review).url == REAL


@requires_db
def test_upsert_repairs_every_platform_row_not_just_one(db):
    """`uq_product_platform` is (product_id, platform, platform_url), so two
    shopee rows for one product are legal. Collapsing them into a dict would
    leave a fabricated URL alive on whichever row lost."""
    marker = uuid.uuid4().hex[:8]
    product = _product(db, f"show_multi_{marker}")
    db.add(ProductPlatform(product_id=product.id, platform=Platform.shopee,
                           platform_url="https://shopee.ph/show_one", is_monetizable=True))
    db.add(ProductPlatform(product_id=product.id, platform=Platform.shopee,
                           platform_url="https://shopee.ph/show_two", is_monetizable=True))
    db.flush()

    seed._upsert_product(db, product.id, product.product_id, product.canonical_name,
                         None, "electronics-tech", REAL, None)
    db.flush()

    rows = db.query(ProductPlatform).filter_by(
        product_id=product.id, platform=Platform.shopee).all()
    urls = {row.platform_url for row in rows}
    assert REAL in urls
    assert not any(u and "show_" in u for u in urls), (
        f"a fabricated URL survived the repair: {urls}")


@requires_db
def test_clearing_a_link_leaves_the_affiliate_relationship_alone(db):
    """`is_monetizable` means an affiliate relationship exists (deviation A6).
    Clearing it here would permanently block a moderator from attaching the
    genuine link, with an error about a relationship that is not the problem."""
    marker = uuid.uuid4().hex[:8]
    product = _product(db, f"show_clear_{marker}")
    db.add(ProductPlatform(product_id=product.id, platform=Platform.shopee,
                           platform_url="https://shopee.ph/show_clear", is_monetizable=True))
    db.flush()

    seed._upsert_product(db, product.id, product.product_id, product.canonical_name,
                         None, "electronics-tech", None, None)
    db.flush()

    row = db.query(ProductPlatform).filter_by(
        product_id=product.id, platform=Platform.shopee).one()
    assert row.platform_url is None
    assert row.is_monetizable is True
