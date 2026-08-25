"""The contributor dashboard's numbers, each traceable to a real source.

Every figure here is computed from something the platform actually records:
commissions for money, `review_view_buckets` for views, `helpful_votes` for
"helped". Where the approved design asks for a number nothing measures, this
returns null and the UI says so — a plausible invented figure on an earnings
screen is worse than an obviously missing one, because a reviewer would make
decisions on it.

WHAT IS DELIBERATELY NULL. Average read time. Measuring it means timing how
long a reader stays on a page, which is reader-behaviour tracking rather than
the aggregate counting the rest of this file does, and it needs a privacy
decision that is the owner's to make rather than engineering's. It is exposed
as null with a reason, so the UI can render the tile honestly instead of
showing a fabricated "4m 3s".
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.commission import Commission
from app.models.review import Review
from app.models.traffic import ReviewViewBucket

ZERO = Decimal("0")

#: Windows the dashboard offers. Capped at 90 days because view buckets are
#: kept for 90 — offering "this year" would draw a view count that is silently
#: zero for most of its span while the earnings beside it are complete.
RANGES: dict[str, int] = {"7d": 7, "30d": 30, "90d": 90}
DEFAULT_RANGE = "7d"

#: Reviews in the ranked list. The design shows three with a "See more".
TOP_REVIEWS = 5


@dataclass(frozen=True)
class SeriesPoint:
    day: date
    amount: Decimal


@dataclass(frozen=True)
class ReviewRow:
    review_id: uuid.UUID
    title: str
    photo_url: str | None
    earnings: Decimal
    views: int
    helped: int
    #: Daily VIEWS across the window, for the sparkline. See `_review_series`
    #: for why views rather than earnings.
    series: list[SeriesPoint] = field(default_factory=list)


@dataclass(frozen=True)
class DashboardSummary:
    range_key: str
    window_start: date
    window_end: date
    #: Net recognised commission for this reviewer, all time. "Estimated"
    #: because a provider can still return an order and reverse it.
    estimated_commission: Decimal
    #: Recognised inside the selected window, net of reversals in it.
    earned_in_window: Decimal
    total_views: int
    #: Always None today: nothing measures read time. Typed as optional rather
    #: than as the literal None so the field can start carrying a value the day
    #: the owner decides reader timing is acceptable, without a schema change.
    average_read_seconds: int | None = None
    unavailable: tuple[str, ...] = ("average_read_seconds",)
    series: list[SeriesPoint] = field(default_factory=list)
    reviews: list[ReviewRow] = field(default_factory=list)
    #: True when this reviewer has never earned anything, so the UI can show a
    #: first-run state rather than a chart of zeroes.
    @property
    def has_earnings(self) -> bool:
        return self.estimated_commission != ZERO or bool(self.series)


def _window(range_key: str, now: datetime | None = None) -> tuple[date, date]:
    if range_key not in RANGES:
        raise ValueError(f"unknown range: {range_key}")
    end = (now or datetime.now(UTC)).date()
    return end - timedelta(days=RANGES[range_key] - 1), end


def summary(db: Session, user_id: uuid.UUID, *, range_key: str = DEFAULT_RANGE,
            now: datetime | None = None) -> DashboardSummary:
    """Everything the dashboard draws, in one pass.

    Reversals are included rather than filtered out, and that is the point: a
    returned sale writes an opposing entry, so summing `reviewer_share` gives
    the NET position. Filtering reversals away would show a reviewer money they
    no longer have.
    """
    start, end = _window(range_key, now)

    lifetime = db.scalar(
        select(func.coalesce(func.sum(Commission.reviewer_share), 0))
        .where(Commission.reviewer_id == user_id)
    ) or ZERO

    in_window = db.scalar(
        select(func.coalesce(func.sum(Commission.reviewer_share), 0))
        .where(Commission.reviewer_id == user_id,
               func.date(Commission.created_at) >= start)
    ) or ZERO

    # Daily net earnings, for the area chart.
    day_rows = db.execute(
        select(func.date(Commission.created_at).label("day"),
               func.coalesce(func.sum(Commission.reviewer_share), 0).label("amount"))
        .where(Commission.reviewer_id == user_id,
               func.date(Commission.created_at) >= start)
        .group_by(func.date(Commission.created_at))
        .order_by(func.date(Commission.created_at))
    ).all()
    by_day = {r.day: Decimal(r.amount) for r in day_rows}
    # Every day in the window, including the empty ones: a chart drawn only
    # from days that had earnings compresses gaps and implies steady activity
    # that did not happen.
    series = [SeriesPoint(day=start + timedelta(days=i),
                          amount=by_day.get(start + timedelta(days=i), ZERO))
              for i in range((end - start).days + 1)]

    views_by_review = dict(db.execute(
        select(ReviewViewBucket.review_id,
               func.coalesce(func.sum(ReviewViewBucket.view_count), 0))
        .join(Review, Review.id == ReviewViewBucket.review_id)
        .where(Review.author_id == user_id,
               func.date(ReviewViewBucket.bucket_start) >= start)
        .group_by(ReviewViewBucket.review_id)
    ).all())

    earnings_by_review = dict(db.execute(
        select(Commission.review_id,
               func.coalesce(func.sum(Commission.reviewer_share), 0))
        .where(Commission.reviewer_id == user_id, Commission.review_id.is_not(None))
        .group_by(Commission.review_id)
    ).all())

    # Rank by earnings, then by views, then by helpfulness — the design's list
    # is an earnings leaderboard, and a reviewer with no earnings yet should
    # still see their most-read work rather than an empty card.
    reviews = list(db.scalars(
        select(Review).where(Review.author_id == user_id,
                             Review.is_removed.is_(False))
    ))
    rows = [
        ReviewRow(
            review_id=r.id, title=r.title, photo_url=r.photo_url,
            earnings=Decimal(earnings_by_review.get(r.id, 0)),
            views=int(views_by_review.get(r.id, 0)),
            helped=int(r.helpful_votes or 0),
            series=_review_series(db, r.id, start, end),
        )
        for r in reviews
    ]
    rows.sort(key=lambda x: (x.earnings, x.views, x.helped), reverse=True)

    return DashboardSummary(
        range_key=range_key, window_start=start, window_end=end,
        estimated_commission=Decimal(lifetime),
        earned_in_window=Decimal(in_window),
        total_views=sum(int(v) for v in views_by_review.values()),
        series=series,
        reviews=rows[:TOP_REVIEWS],
    )


def _review_series(db: Session, review_id: uuid.UUID,
                   start: date, end: date) -> list[SeriesPoint]:
    """Daily VIEWS for one review — what the design's sparkline shows.

    Views rather than earnings, because with a handful of commissions an
    earnings sparkline is a flat line with one spike, which tells a reviewer
    nothing. Views move every day and are the signal the row's other numbers
    ("47k views · 1.3k helped") are already about.
    """
    rows = db.execute(
        select(func.date(ReviewViewBucket.bucket_start).label("day"),
               func.coalesce(func.sum(ReviewViewBucket.view_count), 0).label("n"))
        .where(ReviewViewBucket.review_id == review_id,
               func.date(ReviewViewBucket.bucket_start) >= start)
        .group_by(func.date(ReviewViewBucket.bucket_start))
        .order_by(func.date(ReviewViewBucket.bucket_start))
    ).all()
    by_day = {r.day: Decimal(r.n) for r in rows}
    return [SeriesPoint(day=start + timedelta(days=i),
                        amount=by_day.get(start + timedelta(days=i), ZERO))
            for i in range((end - start).days + 1)]
