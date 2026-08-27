"""The Insights contribution streak and calendar (frame 5762:752).

Owner decision, 2026-08-27: this streak counts days the reviewer **contributed**
— never days they visited or read. No passive-browsing telemetry is added, and
none is implied: every date here comes from a timestamp the application already
persists for its own reasons.

What counts, and the column each day is read from:

    publishing a review          reviews.published_at   (author_id)
    posting a question           questions.created_at   (asker_id)
    posting an answer            answers.created_at     (responder_id)
    a purchase-price observation price_history.created_at (submitted_by)

What does not count: page views, reading, impressions, navigation, and plain
up/down votes. None of those is a documented contribution in this product, and
counting them would turn the streak into the attendance metric the owner
explicitly ruled out.

Two deliberate column choices:

* Reviews are dated by `published_at`, not `created_at`. The contribution is
  publishing, not opening a draft; an unpublished draft contributes nothing.
* Price observations are dated by `created_at`, not `observed_at`.
  `observed_at` is supplied by the submitter and may be backdated, so dating
  the streak by it would let anyone fill in past days at will. `created_at` is
  when the submission actually happened.

Dates are Philippine local dates: a contribution at 07:30 Manila on the 3rd
belongs to the 3rd even though it is 23:30 UTC on the 2nd.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import Date, distinct, func, select, union
from sqlalchemy.orm import Session

from app.core.constants import MANILA
from app.models.product import PriceHistory
from app.models.qa import Answer, Question
from app.models.review import Review

__all__ = [
    "ContributionDay",
    "StreakSummary",
    "contribution_calendar",
    "contribution_dates",
    "insights_streak",
    "streak_from_dates",
    "today_in_manila",
]


@dataclass(frozen=True)
class ContributionDay:
    """One cell of the frame's dot grid."""

    day: date
    contributed: bool


@dataclass(frozen=True)
class StreakSummary:
    current_streak: int
    last_contribution: date | None
    active_today: bool
    calendar: list[ContributionDay]
    calendar_month: date
    total_days: int


def today_in_manila(now: datetime | None = None) -> date:
    """The user-facing 'today'. Internally everything stays UTC."""
    return (now or datetime.now(MANILA)).astimezone(MANILA).date()


def streak_from_dates(days: Iterable[date], today: date) -> int:
    """Consecutive contribution days ending today, or ending yesterday.

    Pure, so the rules can be tested without a database.

    The yesterday anchor is the point of the whole function: at 00:01 Manila a
    reviewer has not had a chance to contribute yet, and a streak that resets
    at midnight would punish them for the clock rather than for stopping. The
    streak only breaks once a full day has passed with nothing in it.
    """
    active = set(days)
    if not active:
        return 0

    yesterday = today - timedelta(days=1)
    if today in active:
        cursor = today
    elif yesterday in active:
        cursor = yesterday
    else:
        return 0

    length = 0
    while cursor in active:
        length += 1
        cursor -= timedelta(days=1)
    return length


def contribution_calendar(
    days: Iterable[date], month: date, today: date | None = None
) -> list[ContributionDay]:
    """Every day of `month`, marked from real contribution dates.

    Days after today are still returned so the grid keeps the month's shape,
    but they are never marked as contributed.
    """
    active = set(days)
    first = month.replace(day=1)
    next_month = (first + timedelta(days=32)).replace(day=1)
    span = (next_month - first).days
    return [
        ContributionDay(
            day=(d := first + timedelta(days=i)),
            contributed=d in active and (today is None or d <= today),
        )
        for i in range(span)
    ]


def contribution_dates(db: Session, user_id) -> set[date]:
    """Distinct Manila dates on which this user contributed something.

    One UNION rather than four round trips, and `DISTINCT` in the database
    rather than in Python: a long-standing contributor has thousands of rows
    and only their dates matter.
    """

    def local_date(column):
        # timezone(zone, timestamptz) -> timestamp in that zone, then to a date.
        return func.timezone("Asia/Manila", column).cast(Date)

    reviews = select(distinct(local_date(Review.published_at)).label("day")).where(
        Review.author_id == user_id, Review.published_at.is_not(None)
    )
    questions = select(distinct(local_date(Question.created_at)).label("day")).where(
        Question.asker_id == user_id, Question.is_removed.is_(False)
    )
    answers = select(distinct(local_date(Answer.created_at)).label("day")).where(
        Answer.responder_id == user_id
    )
    prices = select(distinct(local_date(PriceHistory.created_at)).label("day")).where(
        PriceHistory.submitted_by == user_id
    )

    rows = db.execute(union(reviews, questions, answers, prices)).scalars().all()
    return {row for row in rows if row is not None}


def insights_streak(
    db: Session, user_id, today: date | None = None
) -> StreakSummary:
    """The Streak block's data. Zero days is a real answer, not an error."""
    today = today or today_in_manila()
    days = contribution_dates(db, user_id)
    return StreakSummary(
        current_streak=streak_from_dates(days, today),
        last_contribution=max(days) if days else None,
        active_today=today in days,
        calendar=contribution_calendar(days, today, today),
        calendar_month=today.replace(day=1),
        total_days=len(days),
    )
