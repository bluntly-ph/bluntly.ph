"""Community price observations and the price panel (FR-2).

FR-2 verbatim: *"Price panel from community-submitted purchase price
observations — displayed only when ≥ 3 independent observations exist;
partial-data empty states specified."*

Four decisions follow from that wording and the completion contract, and each
one could reasonably have gone the other way:

**"Independent" means distinct submitters, not distinct rows.** Otherwise one
person could post three observations and unlock the panel alone, which is the
exact failure mode the threshold exists to prevent. `price_history` allows many
rows per user, so the count is over `DISTINCT submitted_by`. A NULL submitter
(a row whose author was deleted) cannot be shown to be independent of anything,
so it never counts toward the threshold — but its price still participates in
the summary once the panel is unlocked, because it was a real observation.

**Only approved observations count.** The completion contract makes every
observation pending until a moderator approves or rejects it (migration 0044),
and the panel is built from approved rows alone. A pending price is counted —
so the UI can say something is waiting — but never priced; a rejected one is
neither.

**Nothing here is scraped.** `price_history` is community-submitted by design
(`docs/schema.md`: "Never scraped"), and the anti-scraping mandate is permanent
(`MILESTONES.md`, owner decision 2026-07-15). This module reads the database and
nothing else; there is no marketplace call anywhere in it.

**The panel reports a range and a median, not an average.** Prices across
platforms and variants are a skewed sample with occasional nonsense at the
edges; a median is what survives one person typing 1 peso or 100,000. The mean
is deliberately not offered, so nobody builds a "market price" claim on it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.models.enums import Platform, PriceObservationSource, PriceObservationStatus
from app.models.product import PriceHistory, Product
from app.models.user import User
from app.schemas.product import PriceObservationDecision, PriceObservationQueueItem

# FR-2: the panel is shown only at or above this many independent observations.
MIN_INDEPENDENT_OBSERVATIONS = 3


@dataclass(frozen=True)
class PricePanel:
    """The computed panel, or the reason it cannot be shown yet."""

    observation_count: int
    independent_count: int
    sufficient: bool
    low: Decimal | None = None
    high: Decimal | None = None
    median: Decimal | None = None
    currency: str = "PHP"
    latest_observed_at: date | None = None
    platforms: tuple[str, ...] = ()
    #: Observations still waiting for a moderator: counted, never priced.
    pending_count: int = 0


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal(2)


def panel_from(rows) -> PricePanel:
    """Build the panel from observations. No database, on purpose.

    FR-2's rule — a price range appears only once at least
    `MIN_INDEPENDENT_OBSERVATIONS` *different people* have reported one — is the
    contractual heart of this feature, and while it lived inside `get_panel` it
    could only be tested against a live Postgres. Every test of it therefore
    skipped in any environment without one, which is most of them.

    Takes anything with `submitted_by`, `price`, `observed_at`, `platform` and
    `status`, so a test can pass plain objects and exercise the rule directly.
    """
    rows = list(rows)
    approved = [r for r in rows if r.status == PriceObservationStatus.approved]
    pending = sum(1 for r in rows if r.status == PriceObservationStatus.pending)
    total = len(approved)
    # Distinct submitters, not rows. One person reporting three times is one
    # observation of the market, and a row whose author has been deleted
    # (`submitted_by` NULL) cannot be shown to be independent of anything.
    independent = len({r.submitted_by for r in approved if r.submitted_by is not None})

    if independent < MIN_INDEPENDENT_OBSERVATIONS:
        # Deliberately no prices in this branch. Returning them "just for the
        # UI to hide" would put unvalidated numbers on the wire, and the panel
        # threshold exists precisely because one or two observations are not
        # yet meaningful.
        return PricePanel(observation_count=total, independent_count=independent,
                          sufficient=False, pending_count=pending)

    prices = [r.price for r in approved]
    return PricePanel(
        observation_count=total,
        independent_count=independent,
        sufficient=True,
        low=min(prices),
        high=max(prices),
        median=_median(prices),
        latest_observed_at=max(r.observed_at for r in approved),
        platforms=tuple(sorted({r.platform.value for r in approved})),
        pending_count=pending,
    )


def new_observation(product_id: uuid.UUID, user_id: uuid.UUID | None, platform: Platform,
                    price: Decimal, observed_at: date, variant: str | None, *,
                    source: PriceObservationSource = PriceObservationSource.manual,
                    review_id: uuid.UUID | None = None) -> PriceHistory:
    """An unsaved, pending observation. Callers own the transaction.

    Separate from `submit_observation` so review submission can add one inside
    its own transaction: a review and the price it reports either both land or
    neither does.
    """
    return PriceHistory(product_id=product_id, submitted_by=user_id,
                        platform=platform, price=price, observed_at=observed_at,
                        variant=variant, source=source, review_id=review_id,
                        status=PriceObservationStatus.pending)


def submit_observation(db: Session, product_id: uuid.UUID, user_id: uuid.UUID,
                       platform: Platform, price: Decimal,
                       observed_at: date, variant: str | None) -> PriceHistory:
    """Record one price observation, pending moderation.

    Repeat submissions from the same person are allowed - a price legitimately
    changes over time - but they do not make that person any more independent,
    which is why the threshold counts distinct submitters rather than rows.
    """
    row = new_observation(product_id, user_id, platform, price, observed_at, variant)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_panel(db: Session, product_id: uuid.UUID) -> PricePanel:
    """The price panel for a product, or an insufficient-data result.

    Always returns a panel object rather than None: "not enough observations
    yet" is a state the UI has to render (FR-2 asks for partial-data empty
    states), and it needs the counts to say how far off it is.
    """
    rows = db.scalars(
        select(PriceHistory).where(PriceHistory.product_id == product_id)
    ).all()
    return panel_from(rows)


def panels_for(db: Session, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, PricePanel]:
    """Panels for several products in one query - the comparison view's need.

    Comparison shows up to four products; asking per product would be four
    round trips to a database in another region for data that one grouped read
    already has. Each group goes through `panel_from`, so the comparison and
    the product page cannot disagree about the threshold.
    """
    if not product_ids:
        return {}
    rows = db.scalars(
        select(PriceHistory).where(PriceHistory.product_id.in_(product_ids))
    ).all()

    grouped: dict[uuid.UUID, list[PriceHistory]] = {pid: [] for pid in product_ids}
    for row in rows:
        grouped.setdefault(row.product_id, []).append(row)
    return {pid: panel_from(items) for pid, items in grouped.items()}


def observation_count(db: Session, product_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count(PriceHistory.id))
        .where(PriceHistory.product_id == product_id)
    ) or 0


# ------------------------------------------------------------- moderation

def _queue_item(row: PriceHistory, product_name: str | None,
                submitter: str | None) -> PriceObservationQueueItem:
    return PriceObservationQueueItem(
        id=row.id, product_id=row.product_id, product_name=product_name,
        platform=row.platform, price=row.price, variant=row.variant,
        observed_at=row.observed_at, source=row.source, status=row.status,
        submitter_username=submitter, decision_note=row.decision_note,
        created_at=row.created_at,
    )


def list_pending(db: Session, *, product_id: uuid.UUID | None,
                 limit: int) -> list[PriceObservationQueueItem]:
    """Oldest first: a price reported earlier is checked earlier."""
    stmt = (
        select(PriceHistory, Product.canonical_name, User.username)
        .join(Product, Product.id == PriceHistory.product_id)
        .outerjoin(User, User.id == PriceHistory.submitted_by)
        .where(PriceHistory.status == PriceObservationStatus.pending)
    )
    if product_id is not None:
        stmt = stmt.where(PriceHistory.product_id == product_id)
    stmt = stmt.order_by(PriceHistory.created_at).limit(limit)
    return [_queue_item(row, name, username) for row, name, username in db.execute(stmt).all()]


def decide_observation(db: Session, observation_id: uuid.UUID, moderator: User,
                       decision: PriceObservationDecision) -> PriceObservationQueueItem:
    """Approve or reject one observation.

    Refuses a moderator deciding their own price — the same self-dealing rule
    as `self_report` and seller claims — and a second decision on a decided
    row, so an approval cannot be silently flipped.
    """
    row = db.get(PriceHistory, observation_id, with_for_update=True)
    if row is None:
        raise NotFoundError("Price observation not found.")
    if row.submitted_by is not None and row.submitted_by == moderator.id:
        raise AppError("You cannot decide a price you submitted.", code="self_decision",
                       status_code=422, title="Invalid decision")
    if row.status != PriceObservationStatus.pending:
        raise AppError("This price has already been decided.",
                       code="price_observation_already_decided", status_code=409,
                       title="Price already decided")

    row.status = (PriceObservationStatus.approved if decision.decision == "approve"
                  else PriceObservationStatus.rejected)
    row.decided_by_id = moderator.id
    row.decided_at = datetime.now(UTC)
    row.decision_note = decision.note
    db.commit()
    db.refresh(row)

    product = db.get(Product, row.product_id)
    submitter = db.get(User, row.submitted_by) if row.submitted_by else None
    return _queue_item(row, product.canonical_name if product else None,
                       submitter.username if submitter else None)
