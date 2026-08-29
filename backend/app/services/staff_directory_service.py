"""Finding a person, for staff.

Moderators already see the whole account population through
GET /admin/reviewers — a list ordered by output, with no way to look anyone up.
That is fine until someone writes in quoting an account and a moderator has to
find them, which today means matching a UUID or the opaque `user_id`
("usr_a3f9c2b1e4") by eye.

So this adds lookup, not visibility: the same population, addressable. Four
ways in, all of them things staff already legitimately hold —

    staff ref     USR-000123, usr 123, 000123, or just 123
    UUID          the canonical primary key, unchanged and still canonical
    email         exact match only
    name          display name or username, partial

WHY EXACT-ONLY FOR EMAIL. A partial email search is a harvesting tool: "@" would
return every account on the platform. Someone who already knows the address can
confirm it; nobody can browse for addresses.

STAFF REF NORMALISATION is generous on input and strict on output. Staff read
these off support tickets, phone calls and screenshots, where they arrive as
"USR-000123", "usr123", "#123" or "123". All of those resolve to the same row.
The canonical form is only ever what the database holds.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.user import User

#: 'USR-' + six digits. The column is varchar(16), so a seventh digit is a
#: pure data change and needs no migration; the pattern below does not assume
#: exactly six.
STAFF_REF_PATTERN = re.compile(r"^USR-\d{6,}$")

#: Anything a human might type for a staff ref: an optional 'usr' or 'user'
#: prefix, optional separators, then digits.
_LOOSE_REF = re.compile(r"^(?:#\s*)?(?:usr|user)?[\s\-_:]*(\d{1,12})$", re.IGNORECASE)


def normalise_staff_ref(raw: str | None) -> str | None:
    """Canonical `USR-000123`, or None if this is not a staff reference.

    Returning None rather than raising is deliberate: the caller uses it to
    decide whether the query LOOKS like a reference at all, and "no" is an
    ordinary answer, not an error.
    """
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    match = _LOOSE_REF.match(text)
    if not match:
        return None
    digits = match.group(1).lstrip("0") or "0"
    # Pad to six, but never truncate: a reference longer than six digits is
    # already canonical at its own width.
    return f"USR-{digits.zfill(6)}"


def looks_like_email(raw: str) -> bool:
    return "@" in raw


def _as_uuid(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(raw.strip())
    except (ValueError, AttributeError, TypeError):
        return None


def _contains_literal(column, value: str):
    """Case-insensitive contains with SQL wildcard characters made literal."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return func.lower(func.coalesce(column, "")).like(
        f"%{escaped.lower()}%", escape="\\")


def search_users(db: Session, query: str, *, limit: int = 25,
                 offset: int = 0) -> tuple[list[User], int]:
    """Staff lookup. Returns (rows, total) for the given query.

    An empty query returns nothing rather than everything. Browsing the whole
    population already exists at /admin/reviewers; this endpoint is for finding
    a known person, and making it double as an unbounded dump would turn one
    careless page into a full account export.
    """
    text = (query or "").strip()
    if not text:
        return [], 0

    clauses = []

    ref = normalise_staff_ref(text)
    if ref is not None:
        clauses.append(User.staff_ref == ref)

    as_uuid = _as_uuid(text)
    if as_uuid is not None:
        clauses.append(User.id == as_uuid)

    if looks_like_email(text):
        # Exact, case-insensitive. Never a prefix or contains match.
        clauses.append(func.lower(User.email) == text.lower())
    else:
        # Names are the only partial match, and only when the input is not an
        # email — so a stray "@" can never widen into a harvest.
        clauses.append(_contains_literal(User.display_name, text))
        clauses.append(_contains_literal(User.username, text))
        # The opaque public id, which staff also see in existing tooling.
        clauses.append(func.lower(func.coalesce(User.user_id, "")) == text.lower())

    predicate = or_(*clauses)
    total = int(db.scalar(select(func.count()).select_from(User).where(predicate)) or 0)
    rows = list(db.scalars(
        select(User).where(predicate)
        # Stable and useful: exact staff-ref and id hits are unique anyway, and
        # for a name search the newest account is the one most likely being
        # asked about. `id` breaks ties so paging cannot repeat or skip a row.
        .order_by(User.created_at.desc(), User.id)
        .limit(limit).offset(offset)
    ).all())
    return rows, total
