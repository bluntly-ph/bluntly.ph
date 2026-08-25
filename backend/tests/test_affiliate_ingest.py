"""The affiliate import money path.

Every test here corresponds to a way this can lose or invent money. Production
currently holds zero commissions, so both of the defects these cover are latent
rather than live — which is exactly when they are cheapest to fix and hardest
to notice.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.commission import Commission
from app.models.enums import Platform, Verdict
from app.models.postback import AffiliatePostback
from app.models.product import Product
from app.models.review import ReferralLink, Review
from app.services import affiliate_ingest
from tests.conftest import make_user, requires_db

SHOPEE_HEADER = (
    "Order id,Order Status,Conversion id,Item id,Model id,Promotion id,"
    "Affiliate Item Status,Refund Amount(₱),Affiliate Net Commission(₱),"
    "Complete Time,Sub_id1"
)


def shopee_csv(*, order="ORD1", status="Completed", item_status="Completed",
               refund="0", commission="100.00", sub_id="", conversion="CNV1",
               promotion="", completed_at="2026-08-01 10:00:00") -> bytes:
    """One Shopee row, with only the columns the importer reads."""
    row = (f"{order},{status},{conversion},ITEM1,MODEL1,{promotion},"
           f"{item_status},{refund},{commission},{completed_at},{sub_id}")
    return f"{SHOPEE_HEADER}\n{row}\n".encode()


def attributed_review(db) -> tuple[Review, str, object]:
    """A published review with an active referral link. Returns (review, sub_id, author)."""
    author = make_user(db)
    product = Product(canonical_name=f"Fixture Product {uuid.uuid4().hex[:6]}")
    db.add(product)
    db.flush()

    review = Review(
        product_id=product.id, author_id=author.id,
        title="Fixture review", discussion="Body text for the fixture.",
        verdict=Verdict.yes_absolutely.value, star_rating=5,
    )
    db.add(review)
    db.flush()

    sub_id = f"blt_{uuid.uuid4().hex[:10]}"
    db.add(ReferralLink(review_id=review.id, platform=Platform.shopee,
                        url="https://shopee.ph/x", sub_id=sub_id, review_version=1))
    db.flush()
    return review, sub_id, author


def _commissions_for(db, sub_id_review: Review) -> list[Commission]:
    return list(db.scalars(select(Commission)
                           .where(Commission.review_id == sub_id_review.id)))


# --- idempotency -----------------------------------------------------------

@requires_db
def test_the_same_order_in_two_different_files_is_credited_once(db):
    """The defect this replaces: the old key is (filename+hash, line number), so
    the same order arriving in a DIFFERENT export is not recognised as a
    duplicate and is credited twice. The provider's own identity is stable
    across files, which is the whole point of keying on it."""
    review, sub_id, _ = attributed_review(db)

    first = shopee_csv(sub_id=sub_id, commission="100.00")
    # A genuinely different file: the export timestamp differs, so the bytes and
    # therefore the OLD file-hash key differ — while the order's own identity is
    # unchanged. Under the old key this is a second, uncaught credit.
    second = shopee_csv(sub_id=sub_id, commission="100.00",
                        completed_at="2026-08-02 11:30:00")
    assert first != second, "the two files must differ, or this proves nothing"

    affiliate_ingest.apply(db, uuid.uuid4(), "first.csv", first)
    summary = affiliate_ingest.apply(db, uuid.uuid4(), "second.csv", second)

    assert summary.recognised == 0, "the second file re-recognised the same order"
    assert len(_commissions_for(db, review)) == 1


@requires_db
def test_pending_never_credits_a_wallet(db):
    """Owner rule: commission is not withdrawable before provider finality."""
    review, sub_id, author = attributed_review(db)
    before = author.wallet_balance or Decimal("0")

    affiliate_ingest.apply(db, uuid.uuid4(), "p.csv", shopee_csv(
        sub_id=sub_id, status="Pending", item_status="Pending"))

    db.refresh(author)
    assert (author.wallet_balance or Decimal("0")) == before
    assert _commissions_for(db, review) == []


# --- reversal --------------------------------------------------------------

@requires_db
def test_a_return_reverses_a_recognised_commission(db):
    """The other defect this replaces: the old parser drops non-payable rows, so
    a return never arrived and the earlier `completed` row stood forever."""
    review, sub_id, author = attributed_review(db)
    affiliate_ingest.apply(db, uuid.uuid4(), "sale.csv",
                           shopee_csv(sub_id=sub_id, commission="100.00"))
    db.refresh(author)
    credited = author.wallet_balance or Decimal("0")
    assert credited > 0, "nothing was recognised, so the reversal proves nothing"

    # Shopee reports a return as a refunded item on an otherwise complete order.
    affiliate_ingest.apply(db, uuid.uuid4(), "return.csv", shopee_csv(
        sub_id=sub_id, commission="100.00", refund="500.00"))

    entries = _commissions_for(db, review)
    reversal = [c for c in entries if c.reverses_commission_id is not None]
    assert len(reversal) == 1, "the return did not produce a reversal entry"

    db.refresh(author)
    assert (author.wallet_balance or Decimal("0")) < credited


@requires_db
def test_the_reversal_is_the_exact_negation_of_its_original(db):
    """A reversal that is not the exact opposite leaves the ledger and the
    wallet quietly disagreeing."""
    review, sub_id, _ = attributed_review(db)
    affiliate_ingest.apply(db, uuid.uuid4(), "sale.csv",
                           shopee_csv(sub_id=sub_id, commission="100.00"))
    affiliate_ingest.apply(db, uuid.uuid4(), "return.csv", shopee_csv(
        sub_id=sub_id, commission="100.00", refund="500.00"))

    entries = _commissions_for(db, review)
    original = next(c for c in entries if c.reverses_commission_id is None)
    reversal = next(c for c in entries if c.reverses_commission_id is not None)

    assert reversal.reverses_commission_id == original.id
    assert reversal.reviewer_share == -original.reviewer_share
    assert reversal.platform_share == -original.platform_share
    assert reversal.honesty_fund_share == -original.honesty_fund_share
    # The pair nets to nothing, which is what "reversed" has to mean.
    assert (original.reviewer_share + reversal.reviewer_share) == 0


@requires_db
def test_a_return_seen_twice_reverses_only_once(db):
    """Providers repeat rows across exports; a second sighting of the same
    return must not claw back the money twice."""
    review, sub_id, _ = attributed_review(db)
    affiliate_ingest.apply(db, uuid.uuid4(), "sale.csv",
                           shopee_csv(sub_id=sub_id, commission="100.00"))
    returned = shopee_csv(sub_id=sub_id, commission="100.00", refund="500.00")
    affiliate_ingest.apply(db, uuid.uuid4(), "return1.csv", returned)
    affiliate_ingest.apply(db, uuid.uuid4(), "return2.csv", returned)

    reversals = [c for c in _commissions_for(db, review)
                 if c.reverses_commission_id is not None]
    assert len(reversals) == 1


# --- the owner's post-payout policy ---------------------------------------

@requires_db
def test_a_post_payout_return_absorbs_the_shortfall_instead_of_creating_debt(db):
    """Owner decision: Bluntly absorbs an unrecoverable return rather than
    pushing a user into debt for a buyer's return they had no part in. The
    wallet must never go negative, and the shortfall must be recorded rather
    than silently forgotten."""
    review, sub_id, author = attributed_review(db)
    affiliate_ingest.apply(db, uuid.uuid4(), "sale.csv",
                           shopee_csv(sub_id=sub_id, commission="100.00"))

    # Simulate the payout: the money has left the wallet before the return.
    db.refresh(author)
    author.wallet_balance = Decimal("0")
    db.flush()

    summary = affiliate_ingest.apply(db, uuid.uuid4(), "return.csv", shopee_csv(
        sub_id=sub_id, commission="100.00", refund="500.00"))

    db.refresh(author)
    assert (author.wallet_balance or Decimal("0")) >= 0, "wallet was driven negative"
    assert summary.unrecovered_amount > 0, "the shortfall was not recorded"

    postback = db.scalar(select(AffiliatePostback).where(
        AffiliatePostback.review_id == review.id))
    assert postback is not None and postback.unrecovered_amount is not None


@requires_db
def test_wallet_balance_never_goes_negative_across_the_whole_flow(db):
    """The database CHECK would catch this by raising; the point of asserting it
    here is that the import must not RELY on the database refusing the write."""
    review, sub_id, author = attributed_review(db)
    affiliate_ingest.apply(db, uuid.uuid4(), "sale.csv",
                           shopee_csv(sub_id=sub_id, commission="100.00"))
    db.refresh(author)
    author.wallet_balance = Decimal("0.01")
    db.flush()
    affiliate_ingest.apply(db, uuid.uuid4(), "return.csv", shopee_csv(
        sub_id=sub_id, commission="100.00", refund="500.00"))
    db.refresh(author)
    assert (author.wallet_balance or Decimal("0")) >= 0


# --- attribution and preview ----------------------------------------------

@requires_db
def test_an_unattributable_sale_is_recorded_but_pays_nobody(db):
    """The sale happened; we just cannot say whose review caused it. Dropping
    the row would hide a real gap in attribution."""
    before = db.execute(select(func.count()).select_from(Commission)).scalar()
    summary = affiliate_ingest.apply(db, uuid.uuid4(), "orphan.csv",
                                     shopee_csv(sub_id="blt_does_not_exist"))
    after = db.execute(select(func.count()).select_from(Commission)).scalar()

    assert summary.unattributed == 1
    assert after == before, "money was recognised with nobody to pay"
    assert db.scalar(select(AffiliatePostback).where(
        AffiliatePostback.review_sub_id == "blt_does_not_exist")) is not None


@requires_db
def test_a_sale_attributable_later_is_still_paid(db):
    """An unattributable completed sale is stored as `completed`, so the next
    import evaluates completed -> completed and gets `none`. Without a retry
    the money is orphaned forever, even once the referral link exists — and
    nothing would ever surface that, because the import reports success."""
    raw = shopee_csv(sub_id="blt_attached_later", commission="100.00")
    first = affiliate_ingest.apply(db, uuid.uuid4(), "orphan.csv", raw)
    assert first.unattributed == 1 and first.recognised == 0

    # The moderator attaches the referral link afterwards.
    author = make_user(db)
    product = Product(canonical_name=f"Later {uuid.uuid4().hex[:6]}")
    db.add(product)
    db.flush()
    review = Review(product_id=product.id, author_id=author.id,
                    title="Attached later", discussion="Body.",
                    verdict=Verdict.yes_absolutely.value, star_rating=5)
    db.add(review)
    db.flush()
    db.add(ReferralLink(review_id=review.id, platform=Platform.shopee,
                        url="https://shopee.ph/x", sub_id="blt_attached_later",
                        review_version=1))
    db.commit()

    second = affiliate_ingest.apply(db, uuid.uuid4(), "again.csv", raw)
    assert second.recognised == 1, "the sale stayed orphaned after attribution"
    assert len(_commissions_for(db, review)) == 1


@requires_db
def test_preview_writes_nothing(db):
    """A moderator is about to move money on the strength of a file they did not
    write. Preview has to be safe to run."""
    _, sub_id, _ = attributed_review(db)
    before_c = db.execute(select(func.count()).select_from(Commission)).scalar()
    before_p = db.execute(select(func.count()).select_from(AffiliatePostback)).scalar()

    summary = affiliate_ingest.preview(db, shopee_csv(sub_id=sub_id))

    assert summary.dry_run is True
    assert summary.recognised == 1, "preview should still say what it WOULD do"
    assert db.execute(select(func.count()).select_from(Commission)).scalar() == before_c
    assert db.execute(
        select(func.count()).select_from(AffiliatePostback)).scalar() == before_p


@requires_db
def test_preview_totals_match_what_the_ledger_would_store(db):
    """Providers report more precision than money has — Shopee's commissions
    carry five decimal places. A preview total that does not match the entries
    written afterwards is worse than no preview."""
    _, sub_id, _ = attributed_review(db)
    raw = shopee_csv(sub_id=sub_id, commission="10.12345")
    previewed = affiliate_ingest.preview(db, raw).recognised_amount
    affiliate_ingest.apply(db, uuid.uuid4(), "x.csv", raw)
    stored = db.scalar(select(Commission.gross_amount)
                       .where(Commission.row_reference.like("ORD1%")))
    assert previewed == stored


# --- the real exports ------------------------------------------------------

@requires_db
@pytest.mark.parametrize("name,expected_rows", [
    ("shopee_commission_report", 108),
    ("lazada_conversion_report", 218),
])
def test_the_owners_real_exports_parse_completely(db, name, expected_rows):
    """Every row is kept, including the ones the old parser dropped as
    unpayable — 11 Lazada returns and 5 Shopee cancellations that a lifecycle
    has to see."""
    import pathlib

    raw = (pathlib.Path(__file__).parent / "fixtures" / f"{name}.csv").read_bytes()
    summary = affiliate_ingest.preview(db, raw)
    assert summary.total_rows == expected_rows
    assert summary.unidentified == 0, "a row could not be given a stable identity"
    assert summary.refused == 0, "a first sighting should never be refused"
