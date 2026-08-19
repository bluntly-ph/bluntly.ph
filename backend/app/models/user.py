"""users, badges, user_badges.

ADR-001: `users` is a PROFILE table keyed to Supabase auth.users.id. There is no
`password_hash` (Supabase owns credentials — ADR-008). `id` is set by the app to
the JWT `sub`; we do NOT hard-FK to auth.users so the identical migration runs on
both local Postgres and Supabase (a Supabase-only FK can be added later).

Deviation (changelog): the spec's per-user `share_percentage` TEXT '40/30/30' is
removed; the split is a single app constant (app.core.constants).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import Language, MemberRole, MembershipTier, MemberType

_TRUST_NAME_EXPR = (
    "CASE trust_stage "
    "WHEN 0 THEN 'Newcomer' WHEN 1 THEN 'Contributor' "
    "WHEN 2 THEN 'Verified Buyer' WHEN 3 THEN 'Established Reviewer' "
    "WHEN 4 THEN 'Trusted Reviewer' WHEN 5 THEN 'Community Expert' "
    "ELSE 'Unknown' END"
)


class User(Base, Timestamps):
    __tablename__ = "users"

    # UUID generated app-side (default) and DB-side (server_default) — ADR-010.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    # Argon2id hash (ADR-011). Nullable so admin/seed accounts can exist w/o a password.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(120))
    # Stable public handle (Slice 1 Phase A). display_name stays the free-text
    # label; username is the unique, URL-safe identity rendered as @handle.
    #
    # NOT NULL in the DB, so the default matters: any code path that builds a
    # User without going through services.username.allocate_username (seeds,
    # fixtures, admin tooling) would otherwise hit an IntegrityError. The
    # fallback is collision-proof rather than pretty; allocate_username supplies
    # a human-readable handle when one can be derived.
    username: Mapped[str | None] = mapped_column(
        String(32), unique=True, index=True,
        default=lambda: f"user_{uuid.uuid4().hex[:16]}")
    # Public URL of an object in the Supabase Storage `avatars` bucket.
    avatar_url: Mapped[str | None] = mapped_column(Text)
    # Onboarding step 2 ("What do you shop for?") — category slugs that seed the
    # user's feed. Free-form to match products.category, which is also a plain
    # string rather than an enum.
    interests: Mapped[list[str] | None] = mapped_column(JSONB)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Membership tier (M1) — Special/Founding/Standard. Distinct from trust stage.
    membership_tier: Mapped[MembershipTier] = mapped_column(
        Enum(MembershipTier, name="membership_tier"),
        default=MembershipTier.standard, nullable=False,
        server_default=MembershipTier.standard.value,
    )
    role: Mapped[MemberRole] = mapped_column(
        Enum(MemberRole, name="member_role"), default=MemberRole.user, nullable=False,
        server_default=MemberRole.user.value,
    )
    member_type: Mapped[MemberType] = mapped_column(
        Enum(MemberType, name="member_type"), default=MemberType.shopper, nullable=False,
        server_default=MemberType.shopper.value,
    )
    language: Mapped[Language] = mapped_column(
        Enum(Language, name="language"), default=Language.en, nullable=False,
        server_default=Language.en.value,
    )

    # Trust progression (FR-7). reputation_score is 0..100 (ADR-003).
    reputation_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=0, nullable=False, server_default="0"
    )
    trust_stage: Mapped[int] = mapped_column(
        SmallInteger, default=0, nullable=False, server_default="0"
    )
    trust_level_name: Mapped[str] = mapped_column(
        String(32), Computed(_TRUST_NAME_EXPR, persisted=True)
    )

    # Behavioural aggregates feeding reputation_score / stage unlocks.
    verified_review_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    helpfulness_ratio: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=0, server_default="0"
    )
    best_answer_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    strikes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_on_probation: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # seller_aggregates and seller_trust_score were the denormalized mirrors of
    # seller_reviews (M2 slice 4). Seller trust ratings were withdrawn from
    # contract on 2026-07-28 and the table is dropped by migration 0024; with
    # their source gone these could only ever hold stale numbers, and a stale
    # trust score is worse than none.
    #
    # Removed from the model BEFORE the migration drops the columns. Doing it
    # the other way round is what took the API down on 2026-08-19: SQLAlchemy
    # emits every mapped column in its SELECT, so a column the model still
    # declares but the database no longer has fails every read of this table.

    # Earnings.
    wallet_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=0, nullable=False, server_default="0"
    )
    # Token economy (M2 slice 7): mirrors the append-only token_transactions ledger.
    token_balance: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default="0"
    )
    # payout_account is sensitive personal data (RA 10173) — PayPal email.
    payout_account: Mapped[str | None] = mapped_column(String(320))

    account_matured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    badges: Mapped[list[UserBadge]] = relationship(back_populates="user",
                                                   cascade="all, delete-orphan")


class Badge(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "badges"

    badge_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(255))
    criteria: Mapped[dict | None] = mapped_column(JSONB)


class UserBadge(Base, UUIDPrimaryKey):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    badge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("badges.id", ondelete="CASCADE"), nullable=False
    )
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="badges")
    badge: Mapped[Badge] = relationship()
