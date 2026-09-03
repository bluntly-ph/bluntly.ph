"""review_reading_sessions — one row per review impression, merged in place.

IDENTITY IS TWO COLUMNS, NEVER ONE. `reader_ref` holds a real account;
`anon_ref` holds a rotating 24-hour pseudonym with no preimage. Exactly one is
non-null, enforced by CHECK constraints in migration 0041. This prevents a
direct account-to-pseudonym linkage key; raw access remains restricted because
time, content, and coarse-country correlations can still permit inference.

COLLECTION ONLY. Nothing in this table is read by any code that computes a
score, a rank, a moderator priority, a publication decision, a vote weight, a
fund share, or a payout. `tests/test_telemetry_isolation.py` asserts that.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ReaderKind


class ReviewReadingSession(Base):
    __tablename__ = "review_reading_sessions"
    __table_args__ = (
        CheckConstraint(
            "(reader_kind = 'user') = (reader_ref IS NOT NULL)",
            name="ck_reading_reader_user",
        ),
        CheckConstraint(
            "(reader_kind = 'anon') = (anon_ref IS NOT NULL)",
            name="ck_reading_reader_anon",
        ),
        CheckConstraint(
            "scroll_milestone IN (0,25,50,75,100)",
            name="ck_reading_scroll",
        ),
        CheckConstraint("device_class BETWEEN 0 AND 3", name="ck_reading_device"),
        CheckConstraint(
            "active_ms >= 0 AND body_active_ms >= 0 AND wall_ms >= 0",
            name="ck_reading_ms_signs",
        ),
        CheckConstraint("body_active_ms <= active_ms", name="ck_reading_body_le_act"),
        CheckConstraint(
            "active_ms <= 1800000 AND body_active_ms <= 1800000 "
            "AND wall_ms <= 1800000",
            name="ck_reading_duration_cap",
        ),
        CheckConstraint(
            "checkpoints BETWEEN 1 AND 16 AND max_seq >= 0",
            name="ck_reading_checkpoint_cap",
        ),
        CheckConstraint(
            "(vote_client_after_ms IS NULL OR vote_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(report_client_after_ms IS NULL OR report_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(comment_client_after_ms IS NULL OR comment_client_after_ms BETWEEN 0 AND "
            "1800000) AND "
            "(share_client_after_ms IS NULL OR share_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(photo_client_after_ms IS NULL OR photo_client_after_ms BETWEEN 0 AND 1800000) AND "
            "(outlink_client_after_ms IS NULL OR outlink_client_after_ms BETWEEN 0 AND "
            "1800000) AND "
            "(active_ms_at_first_vote IS NULL OR active_ms_at_first_vote BETWEEN 0 AND 1800000)",
            name="ck_reading_interaction_cap",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    #: Client-generated. Trusted ONLY to group checkpoints and dedupe replays.
    impression_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )

    reader_kind: Mapped[ReaderKind] = mapped_column(
        Enum(ReaderKind, name="reader_kind"), nullable=False
    )
    reader_ref: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    anon_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    #: SERVER CLOCK ONLY. The client never sends an absolute timestamp, which
    #: removes the whole class of clock-skew and backdating attacks.
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    active_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    body_active_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    wall_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    scroll_milestone: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    checkpoints: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    max_seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    clamped: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    #: Client-asserted, first-occurrence-wins. Named so nobody mistakes these
    #: for server truth; `first_vote_at` below is the trustworthy half.
    vote_client_after_ms: Mapped[int | None] = mapped_column(Integer)
    report_client_after_ms: Mapped[int | None] = mapped_column(Integer)
    comment_client_after_ms: Mapped[int | None] = mapped_column(Integer)
    share_client_after_ms: Mapped[int | None] = mapped_column(Integer)
    #: Defined, deliberately unwired in Phase 1: the review page renders images
    #: through non-interactive next/image, so there is no photo-open control to
    #: instrument. Present so a future lightbox needs no schema change.
    photo_client_after_ms: Mapped[int | None] = mapped_column(Integer)
    outlink_client_after_ms: Mapped[int | None] = mapped_column(Integer)

    first_vote_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_ms_at_first_vote: Mapped[int | None] = mapped_column(Integer)

    #: Coarse geography: COUNTRY ONLY. City beside a pseudonym would be a
    #: location trail; city stays in the identity-free hourly aggregates.
    country: Mapped[str | None] = mapped_column(String(2))

    #: Confound controls snapshotted at write time, because a review can be
    #: edited and a residual computed against the current text would compare a
    #: reader's behaviour to words they never saw.
    word_count_at_view: Mapped[int | None] = mapped_column(SmallInteger)
    star_rating_at_view: Mapped[int | None] = mapped_column(SmallInteger)
    #: 0 unknown / 1 phone / 2 tablet / 3 desktop. Derived server-side from the
    #: request User-Agent, which is NEVER persisted.
    device_class: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
