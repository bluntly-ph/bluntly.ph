"""Integration tests (require a migrated Postgres):
  * all 15 Data Dictionary tables exist,
  * earn_eligible_votes snapshots are immutable under later trust changes.

Run `alembic upgrade head` against the test DB first (docker-compose does this).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import delete, inspect

from app.db.session import SessionLocal, engine
from app.models import EarnEligibleVote, Product, Review, User
from app.models.enums import Verdict, VoteDirection
from tests.conftest import requires_db

# The M0 core. `seller_reviews` was here until `0024_drop_seller_reviews`
# removed it: FR-4 was descoped by the owner, so the table is gone by decision
# rather than by accident. The test kept asserting it for as long as it kept
# being skipped, and failed the first time it ran against a real database.
EXPECTED_TABLES = {
    "users", "badges", "user_badges", "products", "product_platforms",
    "price_history", "reviews", "questions", "answers",
    "sessions", "commissions", "honesty_fund_distributions", "moderation_logs",
    "earn_eligible_votes",
}


@requires_db
def test_the_core_tables_are_present():
    tables = set(inspect(engine).get_table_names())
    missing = EXPECTED_TABLES - tables
    assert not missing, f"Missing tables: {missing}"
    assert len(EXPECTED_TABLES) == 14
    assert "seller_reviews" not in tables, (
        "seller_reviews is back; FR-4 was descoped and 0024 dropped it")


@requires_db
def test_vote_weight_snapshot_is_immutable():
    db = SessionLocal()
    try:
        voter = User(id=uuid.uuid4(), email=f"voter_{uuid.uuid4().hex}@example.com",
                     display_name="Voter", trust_stage=2, reputation_score=Decimal("60.00"))
        product = Product(canonical_name="Test Power Bank", category="electronics")
        db.add_all([voter, product])
        db.flush()

        review = Review(product_id=product.id, title="t", discussion="d",
                        verdict=Verdict.it_depends, star_rating=4)
        db.add(review)
        db.flush()

        vote = EarnEligibleVote(
            review_id=review.id, voter_id=voter.id, vote=VoteDirection.up,
            vote_weight=Decimal("0.6000"), trust_stage_snapshot=2,
            trust_score_snapshot=Decimal("60.00"), account_age_days_snapshot=120,
            is_probation_snapshot=False,
        )
        db.add(vote)
        db.commit()
        # Capture ids as plain values before expiring ORM state.
        vote_id, product_id, voter_id = vote.id, product.id, voter.id

        # Later: the voter's trust changes dramatically.
        voter.trust_stage = 5
        voter.reputation_score = Decimal("99.00")
        db.commit()

        db.expire_all()
        refreshed = db.get(EarnEligibleVote, vote_id)
        assert refreshed.vote_weight == Decimal("0.6000")
        assert refreshed.trust_stage_snapshot == 2
        assert refreshed.trust_score_snapshot == Decimal("60.00")
        assert refreshed.account_age_days_snapshot == 120

        # Cleanup via core deletes; deleting the product cascades to review + vote.
        db.expunge_all()
        db.execute(delete(Product).where(Product.id == product_id))
        db.execute(delete(User).where(User.id == voter_id))
        db.commit()
    finally:
        db.close()
