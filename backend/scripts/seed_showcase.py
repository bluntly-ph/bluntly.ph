"""Showcase seed — a handful of realistic, published reviews so the wired UI
looks production-quality instead of the synthetic load-test data.

ADDITIVE and REPAIRING, and idempotent either way. Deterministic UUIDs and
existence guards mean a plain re-run adds nothing new.

It is no longer true that this script never edits an existing row: the first
version of it published fabricated affiliate URLs (``shopee.ph/show_jisulife
?af=bluntly``) that reached production and became QA-006, and repairing those
means writing to rows that already exist. Exactly four columns are ever updated,
and only on rows inside the showcase namespace:

    product_platforms.platform_url   cleared when no real link exists
    reviews.affiliate_link           set to the real link, or cleared
    reviews.earn_eligible_status     monetized <-> approved/honesty_fund
    referral_links.status/url        revoked, or repointed at the real link

Nothing outside ``show_*`` / ``rev_show_*`` is read for mutation, and there is no
DELETE anywhere in this file. Everything it adds uses the
``00000000-0000-0000-0000-0000000c/d/e****`` UUID ranges and ``show_*`` /
``rev_show_*`` business ids, so it is trivial to remove:

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
from urllib.parse import urlsplit

from app.core.config import settings
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
from app.services.review_service import recompute_product_aggregates
from app.services.trust_service import recompute_user_trust
from app.services.vote_service import recompute_review_vote_aggregates

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
    (_u(4), "marites", "Marites Bautista", 2, 11),
    (_u(5), "kervin", "Kervin Dela Cruz", 4, 63),
    (_u(6), "nadine", "Nadine Ilagan", 3, 27),
]

#: A marketplace URL that leads nowhere.
#:
#: The first seed invented one per product — `shopee.ph/show_jisulife?af=bluntly`
#: — and those reached production, where QA-006 found readers landing on Shopee's
#: "This shop failed to load". A made-up affiliate URL is worse than no buy
#: button: the reader blames the platform, and the reviewer's commission path is
#: silently broken. `_real_marketplace_url` rejects anything of that shape, and a
#: product with no real link is seeded WITHOUT one rather than with a fake.
_PLACEHOLDER_MARKERS = ("show_", "?af=bluntly", "example.com")


def _real_marketplace_url(url: str | None, *, what: str) -> str | None:
    """The URL if it can actually be visited, else None — never a stand-in.

    The host is checked against ``settings.affiliate_domains``, the same
    allowlist ``referral_service.validate_affiliate_url`` uses when a moderator
    pastes a link. A shape-only check would have accepted a plausible-looking
    host the redirect would then refuse.
    """
    if not url:
        return None
    if not url.startswith("https://"):
        raise ValueError(f"{what}: marketplace URLs must be https ({url!r})")
    if any(marker in url for marker in _PLACEHOLDER_MARKERS):
        raise ValueError(
            f"{what}: {url!r} looks like a placeholder. Seed a real affiliate "
            "link or leave it None — a buy button that 404s is the bug QA-006 "
            "reported."
        )
    host = (urlsplit(url).hostname or "").lower()
    allowed = {d for domains in settings.affiliate_domains.values() for d in domains}
    if not any(host == d or host.endswith("." + d) for d in allowed):
        raise ValueError(
            f"{what}: {host!r} is not an affiliate domain this platform accepts. "
            "The redirect would refuse it, so seeding it would recreate QA-006 "
            "with a different URL."
        )
    return url


#: The six original showcase reviews were seeded `verified` and the E2E suite
#: depends on them. Everything seeded after them is UNVERIFIED, and that is
#: deliberate: a fixture must never present itself as a confirmed real purchase.
#: None of them carries a `receipt_key` either, so `has_receipt` is False and no
#: proof-of-purchase claim exists anywhere in the showcase set.
LEGACY_VERIFIED = frozenset({
    "rev_show_jisulife", "rev_show_macbook", "rev_show_akko",
    "rev_show_anker", "rev_show_cerave", "rev_show_airism",
})


# (uuid, product_id, canonical_name, brand, category, shopee_url, lazada_url)
#
# The two URLs are the REAL affiliate links for this product, as issued by the
# marketplace's own share tool — store them verbatim. They carry the tracking
# that attributes a sale, and a "cleaned up" link earns nothing.
#
# Verbatim is what is STORED, not what the reader is finally sent. `/r/{id}`
# runs every outbound URL through `referral_service.decorate_affiliate_url`,
# which for Lazada re-encodes the query and appends `sub_id1`/`sub_id2` — so the
# eight Lazada links reach the marketplace in a shape no browser had loaded when
# they were resolved. That decorated shape was therefore loaded too, on
# 2026-09-10, and still lands on the right listing:
#
#   s.ZSIo9U?c=t&t=…&sub_id1=rev_show_silverchain&sub_id2=ref_…
#       -> "JewelryPalace Genuine 100% 925 Sterling Silver Necklace …"
#   s.ZSIor7?c=t&t=…&sub_id1=rev_show_wh1000xm5&sub_id2=ref_…
#       -> "Sony WH-1000XM5 … Wireless Noise Canceling Bluetooth Headphones"
#
# Shopee is not in `_SUB_ID_PLATFORMS`, so those ten travel undecorated.
#
# A product with no link yet keeps None on both. Its review is then seeded as
# approved rather than monetized, so the page simply has no buy button instead
# of a broken one.
PRODUCTS = [
    (_p(1), "show_jisulife", "Jisulife Life9 Handheld Fan", "Jisulife",
     "electronics-tech", None, None),
    (_p(2), "show_macbook", "Apple MacBook Air M2 (13-inch)", "Apple",
     "electronics-tech", None, None),
    (_p(3), "show_akko", "Akko 5075B Plus Mechanical Keyboard", "Akko",
     "electronics-tech", None, None),
    (_p(4), "show_anker", "Anker 737 Power Bank (24000mAh)", "Anker",
     "electronics-tech", None, None),
    (_p(5), "show_cerave", "CeraVe Foaming Facial Cleanser", "CeraVe",
     "beauty", None, None),
    (_p(6), "show_airism", "Uniqlo AIRism Crew Neck Tee", "Uniqlo",
     "fashion-accessories", None, None),
    # --- Real-marketplace set (QA-006) ---------------------------------
    #
    # Every link below was resolved to its listing in a real browser on
    # 2026-09-10 and named from the RENDERED product page, never guessed
    # from a URL fragment. The affiliate short links are stored verbatim:
    # the query string is the attribution, and a tidied link earns nothing.
    #
    # There are NO cross-marketplace pairs in the supplied set — no Shopee
    # listing sells the same product as any Lazada one — so each product
    # carries exactly one marketplace link. Lazada links 13 and 14 resolved
    # to the same shoe (New Balance MR530SG) from two sellers: one product,
    # seeded from link 13. Lazada link 18 rendered no product identity in
    # any browser profile and is deliberately unassigned.
    (_p(7), 'show_uratex_classic', 'Uratex Classic Mattress in Tricot Cover (6 inches)',
     'Uratex', 'home-living',
     "https://s.shopee.ph/2gB11yLwBg", None),  # link 1
    (_p(8), 'show_dji_osmo_action6', 'DJI Osmo Action 6 Action Camera',
     'DJI', 'electronics-tech',
     "https://s.shopee.ph/7pt7BWX1Ta", None),  # link 2
    (_p(9), 'show_comfyrest_sofabed', 'Joyce & Diana Comfy Rest Pro Sofa Bed',
     'Joyce & Diana', 'home-living',
     "https://s.shopee.ph/50YvoKBESR", None),  # link 3
    (_p(10), 'show_active_whey', 'ACTIVE Whey Protein 1lb (100% Whey Protein Powder)',
     'ACTIVE', 'health-fitness',
     "https://s.shopee.ph/BTg3RtPcP", None),  # link 4
    (_p(11), 'show_iphone_17', 'Apple iPhone 17',
     'Apple', 'electronics-tech',
     "https://s.shopee.ph/7AdQOJz8uS", None),  # link 5
    (_p(12), 'show_ipad_11th_a16', 'Apple iPad 11th Gen A16 (Wi-Fi)',
     'Apple', 'electronics-tech',
     "https://s.shopee.ph/70K0C1GTxw", None),  # link 6
    (_p(13), 'show_dji_pocket4', 'DJI Pocket 4',
     'DJI', 'electronics-tech',
     "https://s.shopee.ph/5focbZpfXp", None),  # link 7
    (_p(14), 'show_seaways_cleaner', 'Seaways All-Purpose Cleaner Spray',
     'Seaways', 'home-living',
     "https://s.shopee.ph/7AdQOLGka4", None),  # link 8
    (_p(15), 'show_mandaue_protector', 'Mandaue Foam Waterproof Mattress Protector',
     'Mandaue Foam', 'home-living',
     "https://s.shopee.ph/3g3YDut67F", None),  # link 9
    (_p(16), 'show_iphone_17_pro', 'Apple iPhone 17 Pro',
     'Apple', 'electronics-tech',
     "https://s.shopee.ph/5focbbM3Z1", None),  # link 10
    (_p(17), 'show_jp_silver_chain', 'JewelryPalace 925 Sterling Silver Chain Necklace',
     'JewelryPalace', 'fashion-accessories',
     None, "https://s.lazada.com.ph/s.ZSIo9U?c=t&t=p-i3NUbtB-sGfp3aj"),  # link 11
    (_p(18), 'show_steam_deck_oled', 'Steam Deck OLED Handheld Console',
     'Valve', 'gaming',
     None, "https://s.lazada.com.ph/s.ZSIokl?c=t&t=p-i4dE7F3-sPq9a3M"),  # link 12
    (_p(19), 'show_nb_530', 'New Balance 530 (MR530SG)',
     'New Balance', 'fashion-accessories',
     None, "https://s.lazada.com.ph/s.ZSIoO2?c=q&t=p-iGrOAoF-s2L7tZLj"),  # link 13
    (_p(20), 'show_mv_hand_soap', "Member's Value Antibacterial Hand Soap, Lavender (500mL)",
     "Member's Value", 'beauty',
     None, "https://s.lazada.com.ph/s.ZSIoMs?c=u&t=p-i5MJJZl-sVFLgf3"),  # link 15
    (_p(21), 'show_ps5_digital', 'Sony PlayStation 5 Digital Edition',
     'Sony', 'gaming',
     None, "https://s.lazada.com.ph/s.ZSIooE?c=q&t=p-i513gmy-s2LOIzFD"),  # link 16
    (_p(22), 'show_puma_ballet_flats', "PUMA Ballet Flats Light Sole (Girls')",
     'PUMA', 'fashion-accessories',
     None, "https://s.lazada.com.ph/s.ZSIopc?c=q&t=p-iGxYwcm-s2LW5WPk"),  # link 17
    (_p(23), 'show_ps5_slim_digital', 'Sony PlayStation 5 Slim Digital Edition',
     'Sony', 'gaming',
     None, "https://s.lazada.com.ph/s.ZSIoJS?c=p&t=p-iGrxS2U-s2LCPx7e"),  # link 19
    (_p(24), 'show_sony_wh1000xm5', 'Sony WH-1000XM5 Wireless Noise Cancelling Headphones',
     'Sony', 'audio',
     None, "https://s.lazada.com.ph/s.ZSIor7?c=t&t=p-i3LFd78-sTFaVqA"),  # link 20
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
    (_r(7), 'rev_show_uratex', 6, 3,
     'Uratex Classic 6-inch — firm, plain, and priced like it',
     Verdict.it_depends, 4, True,
     [
      'Firm support that holds its shape',
      'Light enough for one person to move',
      'Tricot cover is easy to wipe down',
     ],
     [
      'Thin cover; a protector is worth budgeting for',
      'Too firm for most side sleepers',
     ],
     'Spare rooms, first apartments and bunk frames.',
     'Side sleepers and anyone expecting plush or pillow-top comfort.',
     "The budget end of Uratex's range, and it behaves like it: six inches of firm "
     "foam in a thin tricot cover. Support is the selling point, not softness. Worth "
     "pairing with a protector — the cover is the part buyers most often ask about, "
     "and it is not the part doing the work.",
     None, 41, Decimal('0.78000')),
    (_r(8), 'rev_show_osmo6', 7, 1,
     'Osmo Action 6 — the sensor upgrade is the reason to look',
     Verdict.yes_absolutely, 5, True,
     [
      'Larger sensor helps in low light',
      '8K capture leaves room to crop',
      'Rugged enough to mount and forget',
     ],
     [
      'Battery drains fast at the highest capture modes',
      'Accessories add up on top of the body price',
     ],
     'Anyone filming outdoors, on a bike, or in the water.',
     'People who mainly shoot indoors and already carry a capable phone.',
     "The interesting part of this generation is the sensor rather than the headline "
     "resolution — a bigger sensor is what changes a dim shot, and 8K mostly buys room "
     "to crop. As an action camera it is the usual trade: the body is affordable, and "
     "the mounts and spare batteries are where the spend goes.",
     None, 63, Decimal('0.86000')),
    (_r(9), 'rev_show_sofabed', 8, 5,
     'Comfy Rest Pro sofa bed — a guest bed that doubles as seating',
     Verdict.it_depends, 3, True,
     [
      'Converts without tools',
      'Anti-slip base stays put',
      'Ships vacuum-packed, so it fits through a door',
     ],
     [
      'Needs a day or two to fully expand after unpacking',
      'Firmer than a real sofa; the fold line is noticeable',
     ],
     'Small units and condos that need a guest bed occasionally.',
     'Anyone wanting a primary sofa for daily lounging.',
     "A convertible foam piece rather than a sofa with a bed hidden inside it — which "
     "is the right expectation to set. Vacuum packing solves the getting-it-upstairs "
     "problem and creates the other one: give it time to recover its shape before "
     "judging the firmness.",
     None, 28, Decimal('0.72000')),
    (_r(10), 'rev_show_whey', 9, 4,
     'ACTIVE Whey 1lb — a starter tub, priced to try',
     Verdict.it_depends, 3, True,
     [
      'Small size is a low-commitment way to test tolerance',
      'Mixes without a shaker ball',
      'Straightforward ingredient list',
     ],
     ['1lb goes quickly at daily use', 'Flavour range is limited next to imports'],
     "People starting out who don't want to commit to a 5lb tub.",
     'Heavy users, who will find the per-serving cost worse than a bulk tub.',
     "The case for a 1lb tub is that protein powder is a taste-and-tolerance gamble "
     "and this is the cheap way to take it. The case against is arithmetic: at a scoop "
     "a day it does not last, and per serving it loses to the big tubs. Buy it to find "
     "out, not to stock up.",
     None, 34, Decimal('0.70000')),
    (_r(11), 'rev_show_iphone17', 10, 1,
     'iPhone 17 — the base model stops feeling like the compromise',
     Verdict.yes_absolutely, 5, True,
     [
      'The everyday model, not a cut-down one',
      'Battery comfortably lasts a day',
      'Long software support window',
     ],
     [
      'Storage tiers are still where the price climbs',
      'Incremental over the previous generation',
     ],
     'Anyone upgrading from a phone three or more years old.',
     "Last year's iPhone owners — this is not a year worth jumping for.",
     "The base iPhone is the one most people should buy, and this generation makes "
     "that easier to say than it used to be. The upgrade case rests on how old your "
     "current phone is rather than on this year's spec sheet. Pick the storage tier "
     "carefully; that is where the real price decision sits.",
     None, 97, Decimal('0.91000')),
    (_r(12), 'rev_show_ipad11', 11, 2,
     'iPad 11th gen — the right iPad for almost everyone',
     Verdict.yes_absolutely, 4, True,
     [
      'More chip than the base use case needs',
      'Wi-Fi model keeps the price sane',
      'Works with the affordable stylus',
     ],
     [
      'Base storage fills fast if you keep media offline',
      'Not the one for serious desktop-class work',
     ],
     'Students, readers, and anyone who wants a couch computer.',
     'Professionals who need desktop apps — look at the Pro line instead.',
     "The base iPad has quietly become the sensible default: enough chip for "
     "everything most people do on a tablet, at the price that makes a tablet worth "
     "owning at all. The upsell pressure is storage, and it is real — decide before "
     "buying whether your library lives offline.",
     None, 55, Decimal('0.84000')),
    (_r(13), 'rev_show_pocket4', 12, 4,
     'DJI Pocket 4 — a gimbal that fits in a jacket pocket',
     Verdict.yes_absolutely, 5, True,
     [
      'Mechanical stabilisation beats phone software',
      'Larger sensor is a real step up',
      'Pocketable enough to actually carry',
     ],
     ['Small screen makes framing fiddly', 'Proprietary accessories again'],
     'Travel and vlog shooters who want steady footage without a rig.',
     'Anyone who would rather carry one device and already has a good phone.',
     "The pitch is that mechanical stabilisation and a larger sensor beat a phone at "
     "the same task, in something you will still have on you. Both halves matter — a "
     "gimbal left at home stabilises nothing. The trade-offs are the small screen and, "
     "as usual, the accessory ecosystem.",
     None, 47, Decimal('0.83000')),
    (_r(14), 'rev_show_seaways', 13, 3,
     'Seaways all-purpose spray — strong, and treat it that way',
     Verdict.it_depends, 3, True,
     [
      'Cuts kitchen grease without long soaking',
      'One bottle covers several surfaces',
      'Cheap per use',
     ],
     [
      'Strong enough to want gloves and ventilation',
      'Not for every finish — spot-test first',
     ],
     'Kitchen degreasing and oven or glass cleaning.',
     'Delicate or coated surfaces, and anyone sensitive to strong cleaners.',
     "Marketed on decontamination and descaling strength, and that framing is the "
     "useful warning: products that cut grease quickly are rarely gentle. Ventilate, "
     "wear gloves, and spot-test anything coated. Used where it belongs it is cheap "
     "and effective; used everywhere it will find the one finish it ruins.",
     None, 22, Decimal('0.66000')),
    (_r(15), 'rev_show_protector', 14, 5,
     'Mandaue Foam mattress protector — the boring purchase that pays off',
     Verdict.yes_absolutely, 4, True,
     [
      'Waterproof layer without a plastic feel',
      'Machine washable',
      'Cheaper than the mattress it protects',
     ],
     ['Adds a little warmth', 'Fitted skirt can be tight on thicker mattresses'],
     'Households with kids, pets, or a mattress still under warranty.',
     'Anyone who runs hot at night and would notice the extra layer.',
     "This is insurance and it is priced like it. The thing to check before buying is "
     "depth: a fitted skirt fighting a thick mattress is the most common complaint "
     "with every protector, not just this one. The usual trade for waterproofing is a "
     "degree of warmth.",
     None, 31, Decimal('0.75000')),
    (_r(16), 'rev_show_iphone17pro', 15, 1,
     'iPhone 17 Pro — worth it for the camera, not the badge',
     Verdict.it_depends, 4, True,
     [
      'Camera system is the genuine differentiator',
      'Display and build justify the tier',
      'Holds resale value well',
     ],
     [
      'Substantially more than the base model',
      'Heavier in the hand',
      'Most of the gap is invisible in everyday use',
     ],
     'People who shoot a lot and will use the longer lens.',
     'Anyone whose honest answer is messaging, maps and a browser.',
     "The Pro premium buys a camera system and a display, and the honest question is "
     "whether you will use them. For someone photographing regularly the gap is real "
     "and visible. For everyone else the base iPhone does the same job for less, and "
     "the Pro's weight is a daily cost that never shows up on a spec sheet.",
     None, 88, Decimal('0.89000')),
    (_r(17), 'rev_show_silverchain', 16, 3,
     'JewelryPalace 925 chains — hallmark first, style second',
     Verdict.it_depends, 3, True,
     [
      'Sterling silver rather than plate',
      'Several chain styles at one price point',
      'Reasonable entry into real silver',
     ],
     [
      'Silver tarnishes and needs occasional care',
      'Clasps are the usual weak point at this price',
     ],
     'First real-silver buyers and anyone replacing plated jewellery.',
     'People wanting a low-maintenance everyday chain — steel is kinder.',
     "The meaningful claim here is the 925 hallmark: sterling rather than plated, "
     "which is the difference between a chain that survives and one that goes green. "
     "The trade is maintenance — silver tarnishes, and at this price the clasp is what "
     "usually fails first. Check the clasp style before choosing the chain.",
     None, 19, Decimal('0.64000')),
    (_r(18), 'rev_show_steamdeck', 17, 2,
     "Steam Deck OLED — the screen is the whole upgrade, and it's enough",
     Verdict.yes_absolutely, 5, True,
     [
      'OLED panel transforms the handheld experience',
      'Better battery life than the LCD model',
      'Runs a real desktop OS underneath',
     ],
     ['Heavy for long handheld sessions', 'Storage fills fast with modern titles'],
     'PC players who want their existing library portable.',
     'Anyone expecting console-style plug-and-play with no tinkering.',
     "The OLED revision is not a new machine, it is the same machine with the part you "
     "look at fixed — and on a handheld that turns out to matter more than raw "
     "performance. It is still a PC: expect some tinkering, and plan storage before "
     "buying rather than after.",
     None, 72, Decimal('0.88000')),
    (_r(19), 'rev_show_nb530', 18, 4,
     'New Balance 530 — the retro runner that goes with everything',
     Verdict.yes_absolutely, 4, True,
     [
      'Neutral colourway suits most outfits',
      'Comfortable out of the box',
      'Widely stocked, so sizing is easy to check',
     ],
     ['Mesh upper marks easily', 'Not a running shoe despite the shape'],
     'Everyday wear and anyone after a neutral, uncomplicated sneaker.',
     'Runners — buy an actual running model for training.',
     "A retro silhouette that sells on looking right with most things rather than on "
     "performance, and there is nothing wrong with that as long as the expectation is "
     "set. Two listings for this exact model code sit side by side on the marketplace "
     "at different prices, so it is worth comparing sellers before buying.",
     None, 58, Decimal('0.85000')),
    (_r(20), 'rev_show_handsoap', 19, 3,
     "Member's Value hand soap — bulk basics, priced accordingly",
     Verdict.it_depends, 3, True,
     [
      '500mL lasts a household a while',
      'Mild lavender scent, not perfumed',
      'Cheap enough to keep at every sink',
     ],
     [
      'Thin consistency pumps out fast',
      'Antibacterial claims are the usual category marketing',
     ],
     'Households refilling several dispensers.',
     'Anyone with sensitive skin who needs a specific formulation.',
     "A value-brand basic, and the sensible way to judge it is on cost per wash and "
     "scent rather than on the antibacterial labelling, which is standard across the "
     "category. The consistency is thin, so a pump dispenser empties faster than the "
     "volume suggests.",
     None, 15, Decimal('0.61000')),
    (_r(21), 'rev_show_ps5digital', 20, 2,
     'PS5 Digital Edition — cheaper up front, and the catch is obvious',
     Verdict.it_depends, 4, True,
     [
      'Noticeably cheaper than the disc model',
      'Same performance as the disc console',
      'Smaller and lighter without the drive',
     ],
     [
      'No disc drive means no second-hand games',
      'Digital pricing rarely discounts as hard',
     ],
     'Players who already buy digitally and never trade games in.',
     'Anyone who buys used, borrows, or resells physical copies.',
     "The whole decision is the disc drive, and it is arithmetic rather than a "
     "technical question: the saving up front against second-hand and sale pricing "
     "over the console's life. If you have bought a used game in the last year, the "
     "disc model is probably cheaper for you overall.",
     None, 66, Decimal('0.82000')),
    (_r(22), 'rev_show_pumaflats', 21, 5,
     'PUMA ballet flats — school-run practical, not dress-up',
     Verdict.it_depends, 3, True,
     [
      'Light sole is genuinely light',
      'Easy on and off for small children',
      'Wipes clean',
     ],
     [
      'Thin sole offers little support for long walking',
      'Sizing runs small — size up',
     ],
     'Everyday wear for kids who need something quick to put on.',
     'Long days on hard ground, where a supportive sole matters more.',
     "A light, simple flat that trades support for convenience — a reasonable trade "
     "for short trips and a poor one for a day out walking. Sizing is the recurring "
     "note across listings for this style, so measure rather than assume.",
     None, 12, Decimal('0.58000')),
    (_r(23), 'rev_show_ps5slim', 22, 1,
     'PS5 Slim Digital — the same decision, in a smaller box',
     Verdict.it_depends, 4, True,
     [
      'Meaningfully smaller than the launch console',
      'Same library and performance',
      'Easier to fit in a media cabinet',
     ],
     [
      'Still no disc drive',
      'Detachable drive is sold separately if you change your mind',
     ],
     'Anyone buying now who is short on shelf space.',
     'People who want a disc drive — buy the disc model outright, not the add-on.',
     "The Slim revision is a packaging change rather than a generational one, so the "
     "buying question is unchanged: digital-only or not. The one thing it adds to that "
     "decision is the option of a separate drive later, which is a worse deal than "
     "buying the disc console up front.",
     None, 44, Decimal('0.80000')),
    (_r(24), 'rev_show_wh1000xm5', 23, 2,
     'Sony WH-1000XM5 — still the default noise-cancelling pick',
     Verdict.yes_absolutely, 5, True,
     [
      'Class-leading noise cancellation',
      'Comfortable enough for long flights',
      'Multipoint pairing works reliably',
     ],
     [
      'No longer folds flat, so the case is bulkier',
      'Premium price outside of sales',
     ],
     'Commuters, flyers, and open-plan office workers.',
     'Anyone needing low-latency audio for gaming or music production.',
     "These remain the reference point the category is measured against, and the "
     "cancellation is the reason. The design change is the real complaint: losing the "
     "fold means a bigger case, which matters exactly as much as how you travel. Worth "
     "waiting for a sale — they discount regularly.",
     None, 81, Decimal('0.90000')),
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


def _upsert_product(db, pid, product_id, name, brand, category, shopee_url, lazada_url):
    """Create the product, and keep its platform links current on re-runs.

    Unlike the authors and reviews below this is a genuine UPSERT: the first
    seed wrote invented marketplace URLs, and a skip-if-present guard would
    leave those in place forever. Only rows in the `show_` namespace are ever
    touched.
    """
    urls = {
        Platform.shopee: _real_marketplace_url(shopee_url, what=f"{product_id} shopee"),
        Platform.lazada: _real_marketplace_url(lazada_url, what=f"{product_id} lazada"),
    }

    product = db.query(Product).filter_by(product_id=product_id).first()
    if product is None:
        product = Product(
            id=pid, product_id=product_id, canonical_name=name, brand=brand,
            category=category, status=ProductStatus.canonicalized,
        )
        db.add(product)
        db.flush()

    # Grouped by platform as a LIST, not a dict. `uq_product_platform` is
    # (product_id, platform, platform_url), so two rows for one platform with
    # different URLs are legal — and with a NULL url Postgres treats every row
    # as distinct, so several are. Collapsing them to one and repairing that
    # one would leave a fabricated URL alive on the row that lost the coin toss.
    existing: dict[Platform, list[ProductPlatform]] = {}
    for row in db.query(ProductPlatform).filter_by(product_id=product.id):
        existing.setdefault(row.platform, []).append(row)

    for platform, url in urls.items():
        rows = existing.get(platform, [])
        if url is None:
            # No real link yet. Keep the row — the product genuinely is sold on
            # this marketplace — and clear the invented URL. `is_monetizable`
            # is deliberately NOT touched: it means "there is an affiliate
            # relationship for this marketplace" (deviation A6), and
            # `referral_service._platform_blocked` refuses a moderator's link
            # for any platform where it is False. Setting it here would answer
            # a question this script has no business answering, and would stop
            # a moderator ever attaching the genuine link by hand.
            for row in rows:
                row.platform_url = None
            continue
        if not rows:
            db.add(ProductPlatform(product_id=product.id, platform=platform,
                                   platform_url=url, is_monetizable=True))
            continue
        # Point the first at the real link and clear any duplicates, so the
        # unique constraint cannot be violated by two identical rows.
        rows[0].platform_url = url
        rows[0].is_monetizable = True
        for row in rows[1:]:
            row.platform_url = None


def _affiliate_for(product_row) -> tuple[Platform | None, str | None]:
    """The marketplace and URL a review of this product should link to.

    A product carries at most one real link in this set, and it decides the
    platform: hardcoding Shopee would have labelled eight Lazada listings as
    Shopee referrals and left them unmonetized, because the Shopee column was
    empty. Shopee wins only when both exist.
    """
    shopee = _real_marketplace_url(product_row[5], what=f"{product_row[1]} shopee")
    lazada = _real_marketplace_url(product_row[6], what=f"{product_row[1]} lazada")
    if shopee:
        return Platform.shopee, shopee
    if lazada:
        return Platform.lazada, lazada
    return None, None


def _sub_id_visible(url: str, sub_id: str | None) -> bool:
    """Whether the sub-id is actually IN the URL, computed rather than assumed.

    `referral_service` derives this honestly (`effective_sub_id in url`) because,
    per the column comment, a false claim here means the monthly marketplace
    report comes back unattributable. A share link like `s.shopee.ph/2gB11yLwBg`
    contains no sub-id, so the honest answer is False.
    """
    return bool(sub_id) and sub_id in url


def _repair_engagement(db, review) -> None:
    """Strip fabricated vote counts from a showcase review (QA-011).

    The first seed wrote `helpful_votes` straight onto the row — 97, 88, 81 —
    with no `review_votes` rows behind them. `vote_service` derives the counts
    from those rows and nothing else, so the first genuine upvote recomputed the
    aggregate from the real data and a review showing "97" dropped to "1". QA
    reported it as the count resetting; it was the fabrication collapsing.

    Zero is the honest figure for a fixture nobody has voted on, and it makes
    the increment correct: 0 -> 1 is exactly what one vote means. Only rows with
    no real votes are touched, so a showcase review that has since been voted on
    keeps the aggregate its voters actually produced.
    """
    if not review.review_id or not review.review_id.startswith("rev_show_"):
        return
    # The service, not three hand-set columns: it derives helpful, unhelpful AND
    # the time-decayed wilson score from the vote rows, which gives 0 for a
    # fixture nobody has voted on and the true total for one people have. That
    # makes the "don't clobber real votes" guard structural rather than a
    # count() precheck, and it cannot go stale if a fourth aggregate is added.
    recompute_review_vote_aggregates(db, review)


def _repair_review_link(db, review, platform, affiliate_url, author_id) -> None:
    """Bring an already-seeded showcase review in line with its real link.

    The first seed published these with an invented affiliate URL, so this runs
    over rows that already exist in production. It only ever touches reviews in
    the `rev_show_` namespace, and it does not rewrite a link a moderator
    attached by hand — those are not seeded rows.

    It also declines to overrule a moderator who has acted on a showcase row.
    An unpublished review is left alone: `referral_service.unpublish` clears
    `published_at` AND moves the status back to `pending` precisely so the row
    stays reachable from the queue, and re-monetizing it here would strand it
    exactly as invariant #8 describes — invisible to readers and absent from
    the queue. A revoked link is likewise left revoked: someone took that
    button down on purpose.
    """
    if not review.review_id or not review.review_id.startswith("rev_show_"):
        return

    links = list(db.query(ReferralLink).filter_by(review_id=review.id))
    active = next((row for row in links if row.status == ReferralLinkStatus.active), None)

    if affiliate_url is None:
        # Nowhere real to send anyone: retract the buy button rather than leave
        # it pointing at a page that fails to load.
        if active is not None:
            active.status = ReferralLinkStatus.revoked
            # The same audit fields `referral_service.revoke_link` writes, so
            # the admin link history does not show a link revoked by nobody for
            # no reason. `revoked_by` is the showcase author because no
            # moderator was involved; the reason says so.
            active.revoked_by = author_id
            active.revoked_at = NOW
            active.revoke_reason = (
                "Fabricated showcase URL retracted by scripts.seed_showcase (QA-006)."
            )
        review.affiliate_link = None
        if review.earn_eligible_status == EarnEligibleStatus.monetized:
            # A low-star review routes to the Honesty Fund, never to `approved`
            # — the same rule the insert path below applies.
            review.earn_eligible_status = (
                EarnEligibleStatus.honesty_fund if (review.star_rating or 0) <= 2
                else EarnEligibleStatus.approved
            )
        # The original seed wrote an example.com photo that renders as nothing
        # while the row claims a photo exists. Clear it while we are here; it is
        # display-only and inside the namespace.
        if review.photo_url and "example.com" in review.photo_url:
            review.photo_url = None
        return

    if review.published_at is None or review.is_removed:
        # Unpublished or removed by a moderator. Repointing the link is safe and
        # useful; changing the lifecycle state is not.
        if active is not None:
            active.url = affiliate_url
            active.platform = platform
        return

    if active is None and links:
        # Every link this review has was revoked. That was a decision; adding a
        # fresh active one would silently undo it.
        return

    review.affiliate_link = affiliate_url
    review.earn_eligible_status = EarnEligibleStatus.monetized
    if review.photo_url and "example.com" in review.photo_url:
        review.photo_url = None
    if active is None:
        db.add(ReferralLink(
            review_id=review.id, platform=platform, url=affiliate_url,
            sub_id=review.review_id, sub_id_in_url=_sub_id_visible(affiliate_url, review.review_id),
            status=ReferralLinkStatus.active,
            review_version=review.current_version or 1, created_by=author_id,
        ))
    else:
        active.url = affiliate_url
        active.platform = platform


def seed() -> None:
    db = SessionLocal()
    try:
        for a in AUTHORS:
            _upsert_author(db, *a)
        for p in PRODUCTS:
            _upsert_product(db, *p)
        db.flush()

        touched_authors: set = set()
        for i, (rid, review_id, pidx, aidx, title, verdict, stars, monetized,
                pros, cons, target, anti, discussion, price,
                _helpful, _wilson) in enumerate(REVIEWS):
            pid = PRODUCTS[pidx][0]
            aid = AUTHORS[aidx][0]
            # Monetized means "there is somewhere real to send the reader".
            # The flag in the table above says the review is ELIGIBLE; the link
            # decides whether it actually happens.
            platform, affiliate_url = _affiliate_for(PRODUCTS[pidx])
            monetized = monetized and affiliate_url is not None

            existing = db.query(Review).filter_by(review_id=review_id).first()
            if existing is not None:
                _repair_review_link(db, existing, platform, affiliate_url, aid)
                _repair_engagement(db, existing)
                # `recompute_user_trust` sums Review.helpful_votes per author,
                # so leaving it would keep a reputation derived from the
                # fabrications just removed until the nightly sweep caught up.
                touched_authors.add(aid)
                continue

            status = (EarnEligibleStatus.monetized if monetized
                      else (EarnEligibleStatus.honesty_fund if stars <= 2
                            else EarnEligibleStatus.approved))
            published = NOW - timedelta(days=i + 1, hours=3 * i)
            review = Review(
                id=rid, review_id=review_id, product_id=pid, author_id=aid,
                title=title, discussion=discussion, verdict=verdict,
                target_audience=target, anti_target_audience=anti,
                star_rating=stars, pros=pros, cons=cons,
                # No photo rather than a fake one. `usablePhoto` filters
                # example.com out anyway, so the old value rendered as nothing
                # while claiming in the database that a photo existed.
                photo_url=None,
                price_paid=price,
                verification_status=(VerificationStatus.verified
                                     if review_id in LEGACY_VERIFIED
                                     else VerificationStatus.unverified),
                # Zero, deliberately — see `_repair_engagement` below. The
                # `helpful` and `wilson` columns in the table above are kept
                # only so the tuple shape does not churn; they are not written.
                helpful_votes=0, unhelpful_votes=0,
                wilson_score=Decimal("0"), published_at=published,
                earn_eligible_status=status, current_version=1,
                affiliate_link=affiliate_url if monetized else None,
            )
            db.add(review)
            db.flush()
            if monetized:
                db.add(ReferralLink(
                    review_id=rid, platform=platform,
                    url=affiliate_url,
                    sub_id=review_id,
                    sub_id_in_url=_sub_id_visible(affiliate_url, review_id),
                    status=ReferralLinkStatus.active, review_version=1,
                    created_by=aid,
                ))
            # Denormalized product aggregates. The service function is used
            # rather than hand-setting avg_rating/review_count: it also
            # refreshes trust_score and the aggregated pros/cons, which a
            # hand-rolled version leaves at zero and NULL until the nightly
            # sweep happens to touch the row.
            db.flush()
            recompute_product_aggregates(db, pid)

        for author_id in touched_authors:
            recompute_user_trust(db, author_id)

        db.commit()
        print(f"Showcase seed complete: {len(AUTHORS)} authors, {len(PRODUCTS)} products, "
              f"{len(REVIEWS)} published reviews.")
    finally:
        db.close()


if __name__ == "__main__":
    # Refuses production before a single row is touched.
    # `production_is_legitimate=True` does NOT mean "runs in production": every
    # such script still refuses unless the owner passes --allow-production. It
    # means the refusal has an answer.
    #
    # This flipped when QA-006 was found. The original stance — "there is no
    # good reason to seed fixtures into the live site" — was right about
    # seeding and wrong about repair: the fabricated links it warned against
    # were already live, and no script was allowed to remove them. Note that
    # `reset_and_seed`, which TRUNCATES every content table before calling
    # seed(), keeps `production_is_legitimate=False` and must never be given an
    # answer.
    guard_cli("seed_showcase", production_is_legitimate=True)
    seed()
