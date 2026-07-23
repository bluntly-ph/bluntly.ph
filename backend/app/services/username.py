"""Username slugification and collision-safe allocation (Slice 1 Phase A).

`display_name` remains the free-text label; `username` is the stable, unique,
URL-safe handle rendered as @handle. The slug rules here are mirrored in SQL by
migration 0016 so the backfill and the runtime agree.
"""

from __future__ import annotations

import re
import unicodedata
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User

MAX_LENGTH = 32
MIN_LENGTH = 3
_VALID = re.compile(rf"^[a-z0-9_]{{{MIN_LENGTH},{MAX_LENGTH}}}$")


def slugify_username(raw: str) -> str:
    """Lowercase, ASCII-fold, collapse invalid runs to `_`, trim to 32."""
    folded = unicodedata.normalize("NFKD", raw)
    folded = folded.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", folded.lower())
    slug = re.sub(r"_{2,}", "_", slug).strip("_")
    return slug[:MAX_LENGTH]


def is_valid_username(candidate: str) -> bool:
    """Governs user-supplied handles only — never the 0016 backfill."""
    return bool(_VALID.match(candidate))


def _taken(db: Session, candidate: str) -> bool:
    return db.scalar(
        select(User.id).where(func.lower(User.username) == candidate.lower())
    ) is not None


def allocate_username(db: Session, preferred: str | None, email: str,
                      user_id: uuid.UUID) -> str:
    """Pick a free handle: preferred -> email local-part -> user_<short id>."""
    candidates = []
    if preferred:
        candidates.append(slugify_username(preferred))
    candidates.append(slugify_username(email.split("@", 1)[0]))
    candidates.append(f"user_{user_id.hex[:8]}")

    for base in candidates:
        if len(base) < MIN_LENGTH:
            continue
        if not _taken(db, base):
            return base
        for suffix in range(2, 1000):
            trimmed = base[: MAX_LENGTH - len(str(suffix))]
            candidate = f"{trimmed}{suffix}"
            if not _taken(db, candidate):
                return candidate
    # Exhausted every base: fall back to something that cannot collide.
    return f"user_{uuid.uuid4().hex[:16]}"
