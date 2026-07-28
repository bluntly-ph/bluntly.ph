"""Postgres enum types shared by models and migrations.

ADR-005 resolves the spec's undefined `verification_tier` / `member_type` enums.
Only `tier_0` is active at launch; the rest are enumerated now so the schema is
concrete (see the deviations changelog).
"""

from __future__ import annotations

import enum


class MemberRole(str, enum.Enum):
    user = "user"
    seller = "seller"
    moderator = "moderator"


class MemberType(str, enum.Enum):
    shopper = "shopper"
    seller = "seller"
    moderator = "moderator"


class Language(str, enum.Enum):
    en = "en"
    fil = "fil"
    tl_x_taglish = "tl-x-taglish"


class MembershipTier(str, enum.Enum):
    """Membership tiers (M1). Distinct from trust stages (reputation)."""

    special = "special"
    founding = "founding"
    standard = "standard"


class ProductStatus(str, enum.Enum):
    pending = "pending"          # submitted via source_url, awaiting canonicalization
    canonicalized = "canonicalized"
    rejected = "rejected"


class Platform(str, enum.Enum):
    shopee = "shopee"
    lazada = "lazada"
    amazon = "amazon"   # M2: affiliate attribution for Amazon
    other = "other"


class ReferralLinkStatus(str, enum.Enum):
    active = "active"
    revoked = "revoked"


class Verdict(str, enum.Enum):
    yes_absolutely = "yes_absolutely"
    it_depends = "it_depends"
    hard_pass = "hard_pass"


class VerificationStatus(str, enum.Enum):
    verified = "verified"
    unverified = "unverified"


class VerificationTier(str, enum.Enum):
    tier_0 = "tier_0"
    tier_1 = "tier_1"


class EarnEligibleStatus(str, enum.Enum):
    none = "none"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    monetized = "monetized"       # >=3 stars -> affiliate link attached
    honesty_fund = "honesty_fund"  # <=2 stars -> Honesty Fund pool


class QuestionDirectedTo(str, enum.Enum):
    buyers = "buyers"
    seller = "seller"


class ConversionStatus(str, enum.Enum):
    clicked = "clicked"
    converted = "converted"
    cancelled = "cancelled"


class CommissionTarget(str, enum.Enum):
    review = "review"
    answer = "answer"


class ModerationTargetType(str, enum.Enum):
    review = "review"
    answer = "answer"
    seller_review = "seller_review"
    question = "question"
    user = "user"


class ModerationAction(str, enum.Enum):
    report = "report"
    approve = "approve"
    reject = "reject"
    remove = "remove"
    penalize = "penalize"
    suspend = "suspend"
    restore = "restore"
    override = "override"
    escalate = "escalate"
    # Admin/audit actions (moderation_logs doubles as the audit log — see changelog).
    csv_import = "csv_import"
    payout = "payout"
    honesty_fund_distribution = "honesty_fund_distribution"
    # Referral link flow (M2 slice 1).
    affiliate_link_attach = "affiliate_link_attach"
    affiliate_link_revoke = "affiliate_link_revoke"
    publish = "publish"
    unpublish = "unpublish"


class ModerationReason(str, enum.Enum):
    fake_proof = "fake_proof"
    plagiarized = "plagiarized"
    spam = "spam"
    harassment = "harassment"
    conflict_of_interest = "conflict_of_interest"
    seller_posing_as_buyer = "seller_posing_as_buyer"
    other = "other"


class VoteDirection(str, enum.Enum):
    up = "up"
    down = "down"


class TokenKind(str, enum.Enum):
    """Token ledger entry kinds (M2 slice 7; request-board kinds added M3 slice 9)."""

    earn_review_published = "earn_review_published"
    earn_commission = "earn_commission"
    admin_grant = "admin_grant"
    admin_deduct = "admin_deduct"
    adjustment = "adjustment"
    # M3 slice 9 — request board escrow/reward flow.
    spend_request_escrow = "spend_request_escrow"
    earn_request_reward = "earn_request_reward"
    refund_request_escrow = "refund_request_escrow"
    platform_topup = "platform_topup"


class PayoutStatus(str, enum.Enum):
    """Payout lifecycle (M3 slice 11). The wallet is debited at `scheduled` and
    refunded on `failed`/`cancelled` — so scheduled/processing/paid are all
    'money has left the wallet' states."""

    scheduled = "scheduled"
    processing = "processing"
    paid = "paid"
    failed = "failed"
    cancelled = "cancelled"


class PayoutMethod(str, enum.Enum):
    paypal_sandbox = "paypal_sandbox"
    paypal_live = "paypal_live"
    manual = "manual"


class ContractStatus(str, enum.Enum):
    """Monetized-review revenue-share contract lifecycle (M3 slice 10)."""

    active = "active"
    expired = "expired"
    bought_out = "bought_out"


class RequestStatus(str, enum.Enum):
    """Review-request lifecycle (M3 slice 9)."""

    open = "open"
    fulfilled = "fulfilled"
    cancelled = "cancelled"
    expired = "expired"
    removed = "removed"


class OtpPurpose(str, enum.Enum):
    """What a one-time code authorises (Slice 1 Phase A)."""

    signup = "signup"
    login = "login"


class ImageSource(str, enum.Enum):
    seeded = "seeded"        # one-off backfill script, 2026-07-28
    moderator = "moderator"  # supplied by a human at link-attach time
    none = "none"            # no image resolved


# Human-readable trust stage names (FR-7). Index == trust_stage (0..5).
TRUST_STAGE_NAMES = [
    "Newcomer",
    "Contributor",
    "Verified Buyer",
    "Established Reviewer",
    "Trusted Reviewer",
    "Community Expert",
]
