"""email_otps — one-time codes for passwordless auth (Slice 1 Phase A).

`email` is deliberately NOT a foreign key to `users`: a signup code is issued
before the user row exists.

`attempts` is the authoritative verify limit. The Redis limiter fails open by
design (app/core/rate_limit.py), so a Redis outage must not hand an attacker
unlimited guesses at a 6-digit code.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import OtpPurpose


class EmailOtp(Base):
    __tablename__ = "email_otps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    # Argon2id, via app.core.security.hash_password. Never the plaintext code.
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[OtpPurpose] = mapped_column(
        Enum(OtpPurpose, name="otp_purpose"), nullable=False)
    attempts: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False)
