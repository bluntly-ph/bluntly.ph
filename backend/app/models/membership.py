"""membership_tiers — tier configuration (M1).

Config rows for the three tiers (Special/Founding/Standard) so an admin can manage
their parameters. `code` matches the `MembershipTier` enum stored on `users`.
`revenue_share_bps` is the reviewer's revenue share in basis points (e.g. 3000 = 30%)
and feeds the tier-based revenue split (M2).
"""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.enums import MembershipTier


class MembershipTierConfig(Base, UUIDPrimaryKey, Timestamps):
    __tablename__ = "membership_tiers"

    code: Mapped[MembershipTier] = mapped_column(
        Enum(MembershipTier, name="membership_tier"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Reviewer revenue share in basis points (0..10000).
    revenue_share_bps: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3000")
    # Lower number = paid earlier in the payout schedule (M3).
    payout_priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    benefits: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
