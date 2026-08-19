"""Local-dev seed data.

Idempotent: safe to run repeatedly. Seeds the six trust/achievement badges, a
moderator account, a sample shopper, and a few pilot-category (electronics)
products — including one `pending` submission to demonstrate the manual
canonicalization queue (§3.1).

Run: python -m scripts.seed   (with DATABASE_URL pointing at your DB, migrated)
"""

from __future__ import annotations

import uuid

from app.core.env_guard import guard_cli
from app.db.session import SessionLocal
from app.models import Badge, MembershipTierConfig, Product, User
from app.models.enums import (
    MemberRole,
    MembershipTier,
    MemberType,
    Platform,
    ProductStatus,
)
from app.models.product import ProductPlatform

# (code, name, description, reviewer revenue share bps, payout priority)
TIERS = [
    (MembershipTier.special, "Special",
     "Invite-only tier with the highest earning share.", 4000, 1),
    (MembershipTier.founding, "Founding",
     "Early members; elevated share and priority payouts.", 3500, 2),
    (MembershipTier.standard, "Standard",
     "Default tier for all new members.", 3000, 3),
]

BADGES = [
    ("first_responder", "First Responder", "First answer within 24 hours."),
    ("best_answer", "Best Answer", "Answer selected as Best Answer."),
    ("verified_buyer", "Verified Buyer", "Reached Stage 2 — affiliate earning unlocked."),
    ("established_reviewer", "Established Reviewer", "Stage 3 — higher search visibility."),
    ("trusted_reviewer", "Trusted Reviewer", "Stage 4 — gold badge, priority Q&A."),
    ("community_expert", "Community Expert", "Stage 5 — governance voice, highest multiplier."),
]

# Deterministic UUIDs so re-seeding references the same rows.
MOD_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
SHOPPER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b1")


def seed() -> None:
    db = SessionLocal()
    try:
        for badge_id, name, desc in BADGES:
            if not db.query(Badge).filter_by(badge_id=badge_id).first():
                db.add(Badge(badge_id=badge_id, name=name, description=desc))

        for code, name, desc, bps, priority in TIERS:
            if not db.query(MembershipTierConfig).filter_by(code=code).first():
                db.add(MembershipTierConfig(code=code, name=name, description=desc,
                                            revenue_share_bps=bps, payout_priority=priority))

        if not db.get(User, MOD_ID):
            db.add(User(id=MOD_ID, user_id="usr_moderator", email="admin@bluntly.ph",
                        display_name="Platform Admin", role=MemberRole.moderator,
                        member_type=MemberType.moderator))
        if not db.get(User, SHOPPER_ID):
            db.add(User(id=SHOPPER_ID, user_id="usr_shopper", email="shopper@example.ph",
                        display_name="Juan dela Cruz", role=MemberRole.user,
                        member_type=MemberType.shopper))

        if not db.query(Product).filter_by(product_id="prd_powerbank_10k").first():
            p = Product(product_id="prd_powerbank_10k", canonical_name="Aukey 10000mAh Power Bank",
                        brand="Aukey", line="Basix", key_spec="10000mAh", descriptor="Power Bank",
                        category="electronics", status=ProductStatus.canonicalized)
            db.add(p)
            db.flush()
            db.add(ProductPlatform(product_id=p.id, platform=Platform.shopee,
                                   platform_url="https://shopee.ph/example", is_monetizable=True))

        # A pending submission awaiting admin canonicalization (§3.1 queue demo).
        if not db.query(Product).filter_by(source_url="https://shopee.ph/pending-example").first():
            db.add(Product(source_url="https://shopee.ph/pending-example",
                           status=ProductStatus.pending, submitted_by=SHOPPER_ID,
                           category="electronics"))

        db.commit()
        print("Seed complete: badges, moderator, shopper, sample + pending products.")
    finally:
        db.close()


if __name__ == "__main__":
    # Refuses production before a single row is touched.
    guard_cli("seed", production_is_legitimate=False)
    seed()
