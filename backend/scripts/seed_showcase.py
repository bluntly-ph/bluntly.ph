"""Showcase seed — a handful of realistic, published reviews so the wired UI
looks production-quality instead of the synthetic load-test data.

ADDITIVE and idempotent. Deterministic UUIDs + existence guards mean re-running
changes nothing and it never edits or deletes existing rows. Everything it adds
uses the ``00000000-0000-0000-0000-0000000c/d/e****`` UUID ranges and
``show_*`` / ``rev_show_*`` business ids, so it is trivial to remove:

    DELETE FROM referral_links WHERE review_id IN
        (SELECT id FROM reviews WHERE review_id LIKE 'rev_show_%');
    DELETE FROM reviews  WHERE review_id  LIKE 'rev_show_%';
    DELETE FROM products WHERE product_id LIKE 'show_%';
    DELETE FROM users    WHERE user_id    LIKE 'usr_show_%';

Run: python -m scripts.seed_showcase
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.env_guard import guard_cli
from app.db.session import SessionLocal
from app.models import Product, User
from app.models.enums import (
    EarnEligibleStatus,
    MemberRole,
    MemberType,
    Platform,
    ProductStatus,
    ReferralLinkStatus,
    Verdict,
    VerificationStatus,
)
from app.models.product import ProductPlatform
from app.models.review import ReferralLink, Review

NOW = datetime.now(UTC)


def _u(n: int) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-0000-0000-0000000c{n:04d}")


def _p(n: int) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-0000-0000-0000000d{n:04d}")


def _r(n: int) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-0000-0000-0000000e{n:04d}")


# (uuid, username, display_name, trust_stage, verified_review_count)
AUTHORS = [
    (_u(1), "viole", "Viole Santos", 3, 42),
    (_u(2), "yuceann", "Yuce Ann", 5, 128),
    (_u(3), "andreo", "Andreo Cruz", 1, 3),
]

# (uuid, product_id, canonical_name, brand, category)
PRODUCTS = [
    (_p(1), "show_jisulife", "Jisulife Life9 Handheld Fan", "Jisulife", "electronics-tech"),
    (_p(2), "show_macbook", "Apple MacBook Air M2 (13-inch)", "Apple", "electronics-tech"),
    (_p(3), "show_akko", "Akko 5075B Plus Mechanical Keyboard", "Akko", "electronics-tech"),
    (_p(4), "show_anker", "Anker 737 Power Bank (24000mAh)", "Anker", "electronics-tech"),
    (_p(5), "show_cerave", "CeraVe Foaming Facial Cleanser", "CeraVe", "beauty"),
    (_p(6), "show_airism", "Uniqlo AIRism Crew Neck Tee", "Uniqlo", "fashion-accessories"),
]

# (uuid, review_id, product_idx, author_idx, title, verdict, stars, monetized,
#  pros, cons, target, anti, discussion, price, helpful, wilson)
REVIEWS = [
    (_r(1), "rev_show_jisulife", 0, 0,
     "Jisulife Life9 — worth the money, or just overhyped?",
     Verdict.it_depends, 4, True,
     ["Genuinely strong airflow", "Light and pocketable", "USB-C, lasts a full commute"],
     ["Loud on the top two speeds", "Nozzle is a little small"],
     "Commuters and anyone surviving Manila heat outdoors.",
     "People who want a quiet fan for a desk — this one whirs.",
     "When you're living in a tropical country like the Philippines, you know it "
     "gets hot — and by hot, we mean hot-hot. The Life9 actually moves air; three "
     "days of MRT commutes and it never dropped below usable on speed 2. It IS "
     "louder than the reviews admit at max, but I'd still buy it again.",
     Decimal("899.00"), 14800, Decimal("0.96000")),
    (_r(2), "rev_show_macbook", 1, 1,
     "MacBook Air M2 — a genuinely lightweight beast",
     Verdict.yes_absolutely, 5, True,
     ["Silent, fanless, never hot", "12+ hour battery is real", "Display is gorgeous"],
     ["8GB base RAM ages fast", "Only two Thunderbolt ports"],
     "Students and creators who work on the go.",
     "Heavy video editors who need sustained power.",
     "Six months of daily driving: Lightroom, 30-tab Chrome, and Figma without a "
     "stutter, and I still end the day at 20%. If you can stretch to 16GB RAM, do "
     "it — otherwise this is the easiest laptop recommendation I can make.",
     Decimal("68990.00"), 9200, Decimal("0.95000")),
    (_r(3), "rev_show_akko", 2, 0,
     "Akko 5075B Plus — the budget board that changed how I type",
     Verdict.yes_absolutely, 5, True,
     ["Sounds premium out of the box", "Gasket mount, hot-swap", "Wireless + wired"],
     ["Stock keycaps could be thicker"],
     "First-time mechanical keyboard buyers.",
     "Travellers who need a compact 60% layout.",
     "I did not expect a sub-₱4k board to feel like this. Pre-lubed switches, a "
     "gasket mount that gives a soft bounce, and it connects over 2.4GHz, Bluetooth, "
     "or cable. Genuinely the best value in this hobby right now.",
     Decimal("3799.00"), 12100, Decimal("0.94000")),
    (_r(4), "rev_show_anker", 3, 2,
     "Anker 737 — charges everything, survives everything",
     Verdict.yes_absolutely, 5, False,
     ["140W output charges a laptop", "24000mAh lasts days", "Smart display for %"],
     ["Heavy — this is a bag power bank, not a pocket one"],
     "Travellers and anyone off-grid for a weekend.",
     "People who just need a light top-up for a phone.",
     "Took this on a 3-day Palawan trip with no reliable outlet. It charged my "
     "phone five times AND topped up my laptop once, and still had bars left. It's "
     "a brick, but it's the brick I trust.",
     Decimal("4999.00"), 6400, Decimal("0.92000")),
    (_r(5), "rev_show_cerave", 4, 1,
     "CeraVe Foaming Cleanser — hype or holy grail?",
     Verdict.it_depends, 4, True,
     ["Doesn't strip the skin", "Ceramides actually help the barrier", "Affordable per mL"],
     ["Foaming formula is too much for dry skin"],
     "Oily and combination skin in humid weather.",
     "Anyone with dry or very sensitive skin — grab the Hydrating one instead.",
     "Three months in and my oily T-zone finally calmed down. It's fragrance-free "
     "and doesn't leave that tight squeaky feeling. If your skin runs dry, though, "
     "this specific (foaming) version will be too stripping — pick the hydrating SKU.",
     Decimal("649.00"), 8700, Decimal("0.90000")),
    (_r(6), "rev_show_airism", 5, 2,
     "Uniqlo AIRism Tee — comfy, but it runs small and pills",
     Verdict.hard_pass, 2, False,
     ["Genuinely cooling fabric"],
     ["Runs a full size small", "Pilled after ~10 washes", "Collar loosened fast"],
     "Nobody I'd point to this specific tee — size up and temper expectations.",
     "Anyone expecting it to last more than a season.",
     "The fabric really is cool to the touch, so I wanted to love it. But mine "
     "pilled under the arms within a month and the collar stretched out. For the "
     "price I expected it to survive a Philippine summer of daily wear. It didn't.",
     None, 2100, Decimal("0.88000")),
]


def _upsert_author(db, uid, username, display_name, stage, count):
    if db.get(User, uid):
        return
    db.add(User(
        id=uid, user_id=f"usr_show_{username}", email=f"{username}@showcase.bluntly.ph",
        username=username, display_name=display_name, role=MemberRole.user,
        member_type=MemberType.shopper, trust_stage=stage, verified_review_count=count,
        reputation_score=Decimal("70") + Decimal(stage) * 5,
    ))


def _upsert_product(db, pid, product_id, name, brand, category):
    if db.query(Product).filter_by(product_id=product_id).first():
        return
    db.add(Product(
        id=pid, product_id=product_id, canonical_name=name, brand=brand,
        category=category, status=ProductStatus.canonicalized,
    ))
    db.flush()
    db.add(ProductPlatform(product_id=pid, platform=Platform.shopee,
                           platform_url=f"https://shopee.ph/{product_id}",
                           is_monetizable=True))
    db.add(ProductPlatform(product_id=pid, platform=Platform.lazada,
                           platform_url=f"https://lazada.com.ph/{product_id}",
                           is_monetizable=True))


def seed() -> None:
    db = SessionLocal()
    try:
        for a in AUTHORS:
            _upsert_author(db, *a)
        for p in PRODUCTS:
            _upsert_product(db, *p)
        db.flush()

        for i, (rid, review_id, pidx, aidx, title, verdict, stars, monetized,
                pros, cons, target, anti, discussion, price, helpful, wilson) in enumerate(REVIEWS):
            if db.query(Review).filter_by(review_id=review_id).first():
                continue
            pid = PRODUCTS[pidx][0]
            aid = AUTHORS[aidx][0]
            status = (EarnEligibleStatus.monetized if monetized
                      else (EarnEligibleStatus.honesty_fund if stars <= 2
                            else EarnEligibleStatus.approved))
            published = NOW - timedelta(days=i + 1, hours=3 * i)
            review = Review(
                id=rid, review_id=review_id, product_id=pid, author_id=aid,
                title=title, discussion=discussion, verdict=verdict,
                target_audience=target, anti_target_audience=anti,
                star_rating=stars, pros=pros, cons=cons,
                photo_url="https://example.com/showcase.jpg",
                price_paid=price,
                verification_status=VerificationStatus.verified,
                helpful_votes=helpful, unhelpful_votes=max(1, helpful // 40),
                wilson_score=wilson, published_at=published,
                earn_eligible_status=status, current_version=1,
                affiliate_link=(f"https://shopee.ph/{PRODUCTS[pidx][1]}?af=bluntly"
                                if monetized else None),
            )
            db.add(review)
            db.flush()
            if monetized:
                db.add(ReferralLink(
                    review_id=rid, platform=Platform.shopee,
                    url=f"https://shopee.ph/{PRODUCTS[pidx][1]}?af=bluntly",
                    sub_id=review_id, sub_id_in_url=True,
                    status=ReferralLinkStatus.active, review_version=1,
                    created_by=aid,
                ))
            # Denormalized product aggregates for a single-review product.
            product = db.get(Product, pid)
            if product is not None:
                product.avg_rating = Decimal(stars)
                product.review_count = 1

        db.commit()
        print(f"Showcase seed complete: {len(AUTHORS)} authors, {len(PRODUCTS)} products, "
              f"{len(REVIEWS)} published reviews.")
    finally:
        db.close()


if __name__ == "__main__":
    # Refuses production before a single row is touched.
    guard_cli("seed_showcase", production_is_legitimate=False)
    seed()
