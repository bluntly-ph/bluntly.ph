"""reviews + review_versions + referral_links.

Publication gate (M2 slice 1, supersedes FR-3 "publish immediately"): a new review
is hidden (`published_at IS NULL`) and auto-queued (`earn_eligible_status=pending`).
A moderator publishes it — either by pasting a referral link (monetized) or via an
explicit no-link publish. A proof photo at submission => verified.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import (
    EarnEligibleStatus,
    Platform,
    ReferralLinkStatus,
    Verdict,
    VerificationStatus,
    VerificationTier,
)


class Review(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "reviews"

    review_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    # Structured format (FR-3).
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    discussion: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[Verdict] = mapped_column(Enum(Verdict, name="verdict"), nullable=False)
    verdict_explanation: Mapped[str | None] = mapped_column(Text)
    target_audience: Mapped[str | None] = mapped_column(Text)
    anti_target_audience: Mapped[str | None] = mapped_column(Text)
    star_rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1..5
    pros: Mapped[list | None] = mapped_column(JSONB)   # max 10 (app-validated)
    cons: Mapped[list | None] = mapped_column(JSONB)   # max 10 (app-validated)

    photo_url: Mapped[str | None] = mapped_column(Text)     # Supabase Storage
    receipt_url: Mapped[str | None] = mapped_column(Text)   # optional post-publish
    price_paid: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status"),
        default=VerificationStatus.unverified, nullable=False,
        server_default=VerificationStatus.unverified.value,
    )
    verification_tier: Mapped[VerificationTier] = mapped_column(
        Enum(VerificationTier, name="verification_tier"),
        default=VerificationTier.tier_0, nullable=False,
        server_default=VerificationTier.tier_0.value,
    )

    # Equal-weight community visibility votes (independent of gate voting, FR-7).
    helpful_votes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    unhelpful_votes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    wilson_score: Mapped[Decimal] = mapped_column(
        Numeric(6, 5), default=0, nullable=False, server_default="0"
    )

    is_removed: Mapped[bool] = mapped_column(default=False, server_default="false")

    # Publication gate (M2 slice 1): NULL = hidden from public; set = live. A new
    # review is created hidden and is published by a moderator action.
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    # earn_eligible pipeline (FR-6).
    earn_eligible_status: Mapped[EarnEligibleStatus] = mapped_column(
        Enum(EarnEligibleStatus, name="earn_eligible_status"),
        default=EarnEligibleStatus.none, nullable=False,
        server_default=EarnEligibleStatus.none.value,
    )
    affiliate_link: Mapped[str | None] = mapped_column(Text)  # attached manually (§3.2)

    # Version history (M1): incremented on every edit; each edit snapshots to
    # review_versions. Starts at 1 on creation.
    current_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class ReviewVersion(Base, UUIDPrimaryKey, Timestamps):
    """Immutable snapshot of a review at a point in time (M1 version history)."""

    __tablename__ = "review_versions"
    __table_args__ = (
        UniqueConstraint("review_id", "version_number", name="uq_review_version"),
    )

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Full snapshot of the editable review fields at this version.
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    edited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    change_note: Mapped[str | None] = mapped_column(Text)


class ReferralLink(Base, UUIDPrimaryKey, Timestamps):
    """Affiliate/referral link history for a review (M2 slice 1).

    `reviews.affiliate_link` mirrors the single active link for fast reads; this
    table is the full audit trail. A partial unique index (in the migration)
    enforces exactly one `active` link per review.
    """

    __tablename__ = "referral_links"

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    platform: Mapped[Platform] = mapped_column(Enum(Platform, name="platform"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # Our affiliate sub-ID (M3 slice 12). The moderator sets this in their
    # affiliate dashboard when generating the link, and the marketplace echoes it
    # back in the monthly report (Shopee `Sub_id1..5`, Lazada `Aff Sub ID` /
    # `Sub ID 1..6`). It is the ONLY field that survives the round trip, so it is
    # what reconciliation matches on — without it a report row cannot be
    # attributed to a reviewer at all. See docs/AFFILIATE_REPORT_FORMATS.md.
    # Not globally unique: a review's links share its sub-ID across revoke ->
    # re-attach. A partial unique index (migration) keeps it unique among ACTIVE
    # links only.
    sub_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # True when the pasted URL visibly contains the sub-ID (best-effort check).
    sub_id_in_url: Mapped[bool] = mapped_column(Boolean, default=False,
                                                server_default="false")
    status: Mapped[ReferralLinkStatus] = mapped_column(
        Enum(ReferralLinkStatus, name="referral_link_status"),
        default=ReferralLinkStatus.active, nullable=False,
        server_default=ReferralLinkStatus.active.value,
    )
    # reviews.current_version at attach time — powers the "edited since monetized" flag.
    review_version: Mapped[int] = mapped_column(Integer, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(Text)
