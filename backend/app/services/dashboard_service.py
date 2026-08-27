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
        # `or bool(self.series)` used to be the second clause, which defeated
        # the purpose stated directly above it: the series is a DENSE range of
        # one point per day and is never empty, so this was always True and the
        # UI drew exactly the chart of zeroes it was meant to prevent — a bare
        # line pinned to the axis, which reads as broken rather than as an empty
        # month. What matters is whether any of the points carry money.
        return (self.estimated_commission != ZERO
                or any(point.amount != ZERO for point in self.series))


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


# ---------------------------------------------------------------------------
# Earnings history (the approved History screen, frame 5762:472)
# ---------------------------------------------------------------------------

#: The frame's filter tabs. They are NOT the canonical vocabulary — they are the
#: reviewer-facing reading of it, and the mapping is stated here rather than
#: guessed at in the UI:
#:
#:   Pending   the marketplace has not finalised the sale, so nothing is earned
#:   To earn   recognised and owed, but not yet paid out
#:   Paid      settled into a payout
#:   Returned  the buyer returned it and the entry was reversed
#:
#: Lifecycle and settlement stay separate underneath; this is a presentation of
#: both, and "To earn" deliberately does NOT say "Completed" — a completed sale
#: that has not been paid is exactly what the reviewer needs told apart.
EARNING_FILTERS = ("all", "pending", "to_earn", "paid", "returned")


@dataclass(frozen=True)
class EarningRow:
    commission_id: str
    occurred_on: date
    review_id: uuid.UUID | None
    review_title: str | None
    product_name: str | None
    photo_url: str | None
    #: What the reviewer receives — their share, not the gross.
    amount: Decimal
    status: str
    #: The breakdown the frame reveals when a row is expanded.
    gross_amount: Decimal
    commission_rate: Decimal | None
    platform_share: Decimal
    honesty_fund_share: Decimal
    reviewer_share: Decimal


@dataclass(frozen=True)
class EarningsHistory:
    #: "Est. All time income" in the frame — the reviewer's share, net of
    #: reversals, across everything.
    all_time: Decimal
    rows: list[EarningRow] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def has_data(self) -> bool:
        return bool(self.rows) or self.all_time != ZERO


def _earning_status(commission, postback) -> str:
    """The reviewer-facing status for one commission.

    Derived from the canonical pair rather than invented: the marketplace's
    lifecycle says whether the sale is real yet, and settlement says whether the
    money has moved. Neither alone answers the reviewer's question.
    """
    if commission.reverses_commission_id is not None:
        return "returned"
    if postback is not None:
        settlement = getattr(postback.settlement_status, "value", postback.settlement_status)
        lifecycle = getattr(postback.canonical_status, "value", postback.canonical_status)
        if settlement == "reversed" or lifecycle == "returned":
            return "returned"
        if settlement == "paid":
            return "paid"
        if lifecycle == "pending":
            return "pending"
    return "to_earn"


def earnings_history(db: Session, user_id: uuid.UUID, *, status: str = "all",
                     limit: int = 50) -> EarningsHistory:
    """The reviewer's own earnings, newest first.

    Reversal entries are not listed as rows of their own. A reviewer reading
    their history wants to see the sale and that it came back, not two entries
    that look like two events — so the original carries the `returned` status
    and the pair still nets to zero in `all_time`.
    """
    if status not in EARNING_FILTERS:
        raise ValueError(f"unknown filter: {status}")

    from app.models.postback import AffiliatePostback
    from app.models.product import Product

    all_time = db.scalar(
        select(func.coalesce(func.sum(Commission.reviewer_share), 0))
        .where(Commission.reviewer_id == user_id)
    ) or ZERO

    reversed_ids = set(db.scalars(
        select(Commission.reverses_commission_id)
        .where(Commission.reviewer_id == user_id,
               Commission.reverses_commission_id.is_not(None))
    ))

    rows = db.execute(
        select(Commission, Review, Product, AffiliatePostback)
        .outerjoin(Review, Review.id == Commission.review_id)
        .outerjoin(Product, Product.id == Review.product_id)
        .outerjoin(AffiliatePostback,
                   AffiliatePostback.reconciled_commission_id == Commission.id)
        .where(Commission.reviewer_id == user_id,
               Commission.reverses_commission_id.is_(None))
        .order_by(Commission.created_at.desc())
        .limit(200)
    ).all()

    out: list[EarningRow] = []
    counts: dict[str, int] = {k: 0 for k in EARNING_FILTERS if k != "all"}
    for commission, review, product, postback in rows:
        state = ("returned" if commission.id in reversed_ids
                 else _earning_status(commission, postback))
        counts[state] = counts.get(state, 0) + 1
        if status != "all" and state != status:
            continue
        out.append(EarningRow(
            commission_id=commission.commission_id,
            occurred_on=commission.created_at.date(),
            review_id=review.id if review is not None else None,
            review_title=review.title if review is not None else None,
            product_name=product.canonical_name if product is not None else None,
            photo_url=review.photo_url if review is not None else None,
            amount=Decimal(commission.reviewer_share or 0),
            status=state,
            gross_amount=Decimal(commission.gross_amount or 0),
            commission_rate=(postback.commission_rate if postback is not None else None),
            platform_share=Decimal(commission.platform_share or 0),
            honesty_fund_share=Decimal(commission.honesty_fund_share or 0),
            reviewer_share=Decimal(commission.reviewer_share or 0),
        ))

    counts["all"] = sum(v for k, v in counts.items() if k != "all")
    return EarningsHistory(all_time=Decimal(all_time), rows=out[:limit], counts=counts)
