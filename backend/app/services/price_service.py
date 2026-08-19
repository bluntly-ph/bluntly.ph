"""Community price observations and the price panel (FR-2).

FR-2 verbatim: *"Price panel from community-submitted purchase price
observations — displayed only when ≥ 3 independent observations exist;
partial-data empty states specified."*

Three decisions follow from that wording and are worth stating, because each
one could reasonably have gone the other way:

**"Independent" means distinct submitters, not distinct rows.** Otherwise one
person could post three observations and unlock the panel alone, which is the
exact failure mode the threshold exists to prevent. `price_history` allows many
rows per user, so the count is over `DISTINCT submitted_by`. A NULL submitter
(a row whose author was deleted) cannot be shown to be independent of anything,
so it never counts toward the threshold — but its price still participates in
the summary once the panel is unlocked, because it was a real observation.

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
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import Platform
from app.models.product import PriceHistory

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


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal(2)


def submit_observation(db: Session, product_id: uuid.UUID, user_id: uuid.UUID,
                       platform: Platform, price: Decimal,
                       observed_at: date, variant: str | None) -> PriceHistory:
    """Record one price observation. One row per submission, by design.

    Repeat submissions from the same person are allowed - a price legitimately
    changes over time - but they do not make that person any more independent,
    which is why the threshold counts distinct submitters rather than rows.
    """
    row = PriceHistory(product_id=product_id, submitted_by=user_id,
                       platform=platform, price=price,
                       observed_at=observed_at, variant=variant)
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

    total = len(rows)
    independent = len({r.submitted_by for r in rows if r.submitted_by is not None})

    if independent < MIN_INDEPENDENT_OBSERVATIONS:
        # Deliberately no prices in this branch. Returning them "just for the
        # UI to hide" would put unvalidated numbers on the wire, and the panel
        # threshold exists precisely because one or two observations are not
        # yet meaningful.
        return PricePanel(observation_count=total, independent_count=independent,
                          sufficient=False)

    prices = [r.price for r in rows]
    return PricePanel(
        observation_count=total,
        independent_count=independent,
        sufficient=True,
        low=min(prices),
        high=max(prices),
        median=_median(prices),
        latest_observed_at=max(r.observed_at for r in rows),
        platforms=tuple(sorted({r.platform.value for r in rows})),
    )


def panels_for(db: Session, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, PricePanel]:
    """Panels for several products in one query - the comparison view's need.

    Comparison shows up to four products; asking per product would be four
    round trips to a database in another region for data that one grouped read
    already has.
    """
    if not product_ids:
        return {}
    rows = db.scalars(
        select(PriceHistory).where(PriceHistory.product_id.in_(product_ids))
    ).all()

    grouped: dict[uuid.UUID, list[PriceHistory]] = {pid: [] for pid in product_ids}
    for row in rows:
        grouped.setdefault(row.product_id, []).append(row)

    panels: dict[uuid.UUID, PricePanel] = {}
    for pid, items in grouped.items():
        independent = len({r.submitted_by for r in items if r.submitted_by is not None})
        if independent < MIN_INDEPENDENT_OBSERVATIONS:
            panels[pid] = PricePanel(observation_count=len(items),
                                     independent_count=independent, sufficient=False)
            continue
        prices = [r.price for r in items]
        panels[pid] = PricePanel(
            observation_count=len(items), independent_count=independent,
            sufficient=True, low=min(prices), high=max(prices),
            median=_median(prices),
            latest_observed_at=max(r.observed_at for r in items),
            platforms=tuple(sorted({r.platform.value for r in items})),
        )
    return panels


def observation_count(db: Session, product_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count(PriceHistory.id))
        .where(PriceHistory.product_id == product_id)
    ) or 0
