"""The admin Overview screen's figures, each from a real query.

Backs the approved Admin Page frame: four headline counts, a recent-activity
feed, and a queue breakdown. Nothing here is a placeholder — every number is
something the platform already records, and where the design's sub-label
implies a comparison ("+3 from yesterday") the comparison is actually computed
rather than written in.

Manila, not UTC, for anything a person would call "today". A moderator in
Manila approving a review at 08:00 local is 00:00 UTC, so a UTC "today" would
put a whole morning's work on the previous day and make the dashboard disagree
with the moderator's own memory of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.commission import Commission
from app.models.enums import (
    EarnEligibleStatus,
    ModerationAction,
    ModerationTargetType,
    VerificationStatus,
)
from app.models.moderation import ModerationLog
from app.models.review import Review
from app.models.user import User

MANILA = ZoneInfo("Asia/Manila")
ZERO = Decimal("0")

#: Activity rows on the Overview. The design shows five and a "See more".
RECENT_ACTIVITY = 5

#: Actions worth surfacing on an overview. `receipt_view` is deliberately
#: absent: it is an audit record of a moderator opening someone's proof of
#: purchase, and putting it in a feed would advertise private evidence access
#: as if it were routine activity.
FEED_ACTIONS = (
    ModerationAction.approve, ModerationAction.reject, ModerationAction.publish,
    ModerationAction.unpublish, ModerationAction.remove,
    ModerationAction.affiliate_link_attach, ModerationAction.affiliate_link_revoke,
    ModerationAction.csv_import, ModerationAction.payout,
    ModerationAction.honesty_fund_distribution, ModerationAction.escalate,
)


@dataclass(frozen=True)
class ActivityItem:
    action: str
    actor: str | None
    target_ref: str | None
    at: datetime


@dataclass(frozen=True)
class BreakdownBar:
    label: str
    count: int


@dataclass(frozen=True)
class AdminOverview:
    queue_total: int
    #: Queue items somebody has reported. That is what makes one urgent —
    #: not its age, which the queue's own ordering already conveys.
    high_priority: int
    approved_today: int
    #: Signed difference against yesterday, so the UI never has to infer it.
    approved_delta: int
    pending_affiliate: int
    honesty_fund_pool: Decimal
    honesty_fund_month: date
    breakdown: list[BreakdownBar] = field(default_factory=list)
    activity: list[ActivityItem] = field(default_factory=list)

    @property
    def urgent(self) -> int:
        """What the design's "7 urgent" pill counts."""
        return self.high_priority


def _manila_day(moment: datetime | None = None) -> date:
    return (moment or datetime.now(MANILA)).astimezone(MANILA).date()


def _queue_predicate():
    """Reviews genuinely awaiting a moderator.

    Mirrors `get_queue`: pending AND unpublished. Keeping the definition in one
    shape matters — a headline count that disagrees with the list under it is
    worse than no headline at all.
    """
    return (
        Review.is_removed.is_(False),
        Review.published_at.is_(None),
        Review.earn_eligible_status == EarnEligibleStatus.pending,
    )


def _reported_review_ids(db: Session) -> set:
    rows = db.scalars(
        select(ModerationLog.target_ref).where(
            ModerationLog.action == ModerationAction.report,
            ModerationLog.target_type == ModerationTargetType.review,
        )
    )
    # Compared against `str(review.id)`, so they must be strings. As UUIDs the
    # intersection was always empty, which quietly pinned "high priority", the
    # design's "urgent" pill and the Flagged bar to zero no matter how much was
    # reported.
    return {str(r) for r in rows if r}


def _approved_on(db: Session, day: date) -> int:
    """Approvals and publishes on a Manila calendar day."""
    start = datetime.combine(day, datetime.min.time(), tzinfo=MANILA)
    return int(db.scalar(
        select(func.count()).select_from(ModerationLog).where(
            ModerationLog.action.in_(
                (ModerationAction.approve, ModerationAction.publish)),
            ModerationLog.created_at >= start,
            ModerationLog.created_at < start + timedelta(days=1),
        )
    ) or 0)


def overview(db: Session, *, now: datetime | None = None) -> AdminOverview:
    today = _manila_day(now)

    queue = list(db.scalars(select(Review).where(*_queue_predicate())))
    reported = _reported_review_ids(db)
    queue_ids = {str(r.id) for r in queue} | {str(r.review_id) for r in queue}
    high_priority = len(queue_ids & reported)

    approved_today = _approved_on(db, today)
    approved_yesterday = _approved_on(db, today - timedelta(days=1))

    pending_affiliate = int(db.scalar(
        select(func.count()).select_from(Review).where(
            Review.is_removed.is_(False),
            Review.earn_eligible_status == EarnEligibleStatus.approved,
            or_(Review.affiliate_link.is_(None), Review.affiliate_link == ""),
        )
    ) or 0)

    cycle = date(today.year, today.month, 1)
    pool = db.scalar(
        select(func.coalesce(func.sum(Commission.honesty_fund_share), 0))
        .where(Commission.cycle_month == cycle)
    ) or ZERO

    return AdminOverview(
        queue_total=len(queue),
        high_priority=high_priority,
        approved_today=approved_today,
        approved_delta=approved_today - approved_yesterday,
        pending_affiliate=pending_affiliate,
        honesty_fund_pool=Decimal(pool),
        honesty_fund_month=cycle,
        breakdown=_breakdown(db, queue, reported),
        activity=_activity(db),
    )


def _breakdown(db: Session, queue: list[Review], reported: set) -> list[BreakdownBar]:
    """The four bars the design labels, counted over the live queue.

    They deliberately overlap — one review can be both verified and a first
    submission — because they describe WHY items are waiting, not a partition
    of them. A stacked bar would imply the latter.
    """
    if not queue:
        return [BreakdownBar(label, 0) for label in
                ("Earn Eligible", "Flagged", "New Product", "First Submission")]

    author_ids = {r.author_id for r in queue if r.author_id}
    product_ids = {r.product_id for r in queue if r.product_id}

    # Authors with nothing published yet: their first submission.
    published_authors = set(db.scalars(
        select(Review.author_id).where(
            Review.author_id.in_(author_ids or {None}),
            Review.published_at.is_not(None),
            Review.is_removed.is_(False),
        )
    )) if author_ids else set()

    # Products with no published review yet: new to the catalogue.
    reviewed_products = set(db.scalars(
        select(Review.product_id).where(
            Review.product_id.in_(product_ids or {None}),
            Review.published_at.is_not(None),
            Review.is_removed.is_(False),
        )
    )) if product_ids else set()

    return [
        BreakdownBar("Earn Eligible", sum(
            1 for r in queue if r.verification_status == VerificationStatus.verified)),
        BreakdownBar("Flagged", sum(
            1 for r in queue if str(r.id) in reported or str(r.review_id) in reported)),
        BreakdownBar("New Product", sum(
            1 for r in queue if r.product_id not in reviewed_products)),
        BreakdownBar("First Submission", sum(
            1 for r in queue if r.author_id not in published_authors)),
    ]


def _activity(db: Session) -> list[ActivityItem]:
    """The most recent moderator actions, newest first."""
    rows = db.execute(
        select(ModerationLog, User.display_name, User.username)
        .outerjoin(User, User.id == ModerationLog.moderator_id)
        .where(ModerationLog.action.in_(FEED_ACTIONS))
        .order_by(ModerationLog.created_at.desc())
        .limit(RECENT_ACTIVITY)
    ).all()
    return [
        ActivityItem(
            action=log.action.value if hasattr(log.action, "value") else str(log.action),
            actor=display or username,
            # `moderation_logs.target_ref` is a UUID column while this
            # dataclass and the response model both say `str | None`. Pydantic
            # does not coerce UUID to str, so passing it through raised a
            # ValidationError in the route's return statement — outside every
            # guard — and the whole Overview became a bare 500.
            target_ref=str(log.target_ref) if log.target_ref is not None else None,
            at=log.created_at,
        )
        for log, display, username in rows
    ]


@dataclass(frozen=True)
class AffiliateHealth:
    """The affiliate ledger at a glance, kept in two separate axes.

    LIFECYCLE is what the marketplace says happened to the order:
    pending / completed / cancelled / returned.

    SETTLEMENT is what we did about it in our own ledger:
    not_earned / earned / paid / reversed.

    They are reported separately and never summed together, because they answer
    different questions and a single combined bar would imply a progression
    that does not exist — a `completed` order can be `not_earned` (nobody to
    attribute it to), and a `returned` one can be `paid` (the return arrived
    after payout, which is the case the platform absorbs).
    """

    lifecycle: list[BreakdownBar] = field(default_factory=list)
    settlement: list[BreakdownBar] = field(default_factory=list)
    #: Commission recognised, and the part later reversed. Money, not counts.
    recognised_amount: Decimal = ZERO
    reversed_amount: Decimal = ZERO
    #: What returns could not claw back because it had already been paid out.
    #: Bluntly absorbs this; it is surfaced so it is reconciled rather than lost.
    unrecovered_amount: Decimal = ZERO

    @property
    def has_data(self) -> bool:
        return any(b.count for b in self.lifecycle)


#: Fixed order, so a bar does not move between refreshes as counts change.
_LIFECYCLE_ORDER = ("pending", "completed", "cancelled", "returned")
_SETTLEMENT_ORDER = ("not_earned", "earned", "paid", "reversed")


def affiliate_health(db: Session) -> AffiliateHealth:
    """Counts and money across the canonical affiliate store."""
    from app.models.postback import AffiliatePostback

    def _counts(column, order: tuple[str, ...]) -> list[BreakdownBar]:
        rows = db.execute(
            select(column, func.count()).group_by(column)
        ).all()
        found = {
            (v.value if hasattr(v, "value") else str(v)): int(n) for v, n in rows
        }
        return [BreakdownBar(name.replace("_", " ").title(), found.get(name, 0))
                for name in order]

    recognised = db.scalar(
        select(func.coalesce(func.sum(Commission.gross_amount), 0))
        .where(Commission.reverses_commission_id.is_(None))
    ) or ZERO
    # Reversal rows are negative by design, so this is reported as a positive
    # magnitude rather than shown as a negative bar beside a positive one.
    reversed_total = db.scalar(
        select(func.coalesce(func.sum(Commission.gross_amount), 0))
        .where(Commission.reverses_commission_id.is_not(None))
    ) or ZERO
    unrecovered = db.scalar(
        select(func.coalesce(func.sum(AffiliatePostback.unrecovered_amount), 0))
    ) or ZERO

    return AffiliateHealth(
        lifecycle=_counts(AffiliatePostback.canonical_status, _LIFECYCLE_ORDER),
        settlement=_counts(AffiliatePostback.settlement_status, _SETTLEMENT_ORDER),
        recognised_amount=Decimal(recognised),
        reversed_amount=abs(Decimal(reversed_total)),
        unrecovered_amount=Decimal(unrecovered),
    )
