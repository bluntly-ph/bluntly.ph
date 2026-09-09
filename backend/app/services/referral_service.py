"""Referral / affiliate link flow (M2 slice 1) — the manual, moderator-mediated
realization of the `MarketplaceIntegrationService` seam.

The moderator reviews a queued (hidden) review, generates the referral link in
their own affiliate dashboard using the user's product link, and pastes it here —
pasting a valid link both monetizes and publishes the review, atomically.
**No scraping, no marketplace API calls.** If a formal API partnership ever lands,
only this module's internals change.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import AppError
from app.models.enums import (
    EarnEligibleStatus,
    ModerationAction,
    ModerationTargetType,
    Platform,
    ReferralLinkStatus,
    VerificationStatus,
)
from app.models.moderation import ModerationLog
from app.models.product import Product, ProductPlatform
from app.models.review import ReferralLink, Review
from app.models.session import Session as ClickSession
from app.models.user import User
from app.schemas.referral import (
    QueueAuthor,
    QueueCounts,
    QueueItem,
    QueuePage,
    QueuePlatform,
    QueuePriorityAssessment,
    QueuePriorityFactor,
    QueueProduct,
    QueueSignals,
)
from app.schemas.review import ReviewOut
from app.services import fraud_service, report_service
from app.services.contract_service import ensure_contract
from app.services.moderation_priority import (
    PriorityAssessment,
    PriorityBand,
    PriorityFacts,
    PriorityLane,
    SlaState,
    evaluate_priority,
)
from app.services.pii import retention_deadlines
from app.services.review_service import recompute_product_aggregates
from app.services.trust_service import recompute_user_trust

MAX_URL_LEN = 2048


def _now() -> datetime:
    return datetime.now(UTC)


def _conflict(detail: str, code: str) -> AppError:
    return AppError(detail, code=code, status_code=409, title="Conflicting state")


def sub_id_for_review(review_id: uuid.UUID) -> str:
    """The affiliate sub-ID a moderator must set when generating the link.

    Deterministic from the review id so the queue can show it BEFORE the link
    exists (the moderator needs it to create the link in their dashboard), and so
    it is reproducible for support. This is the only identifier that survives the
    round trip into the marketplace's monthly report — see
    docs/AFFILIATE_REPORT_FORMATS.md.
    """
    return f"blt_{review_id.hex[:12]}"


def _award_publish_tokens(db: Session, review: Review) -> None:
    """Slice-7 hook: tokens on first publish. Re-publish after unpublish is a
    no-op via the uq_token_once idempotency index."""
    from app.services.token_service import award_review_published

    if review.author_id is not None:
        award_review_published(db, review.author_id, review.id)


# --- Audit ---
def _audit(db: Session, moderator_id: uuid.UUID, action: ModerationAction,
           review_id: uuid.UUID, notes: str | None = None,
           context: dict | None = None) -> None:
    db.add(ModerationLog(
        log_id=f"mlog_{uuid.uuid4().hex[:10]}",
        target_type=ModerationTargetType.review, target_ref=review_id,
        moderator_id=moderator_id, action=action, notes=notes, context=context,
    ))


# --- Link queries ---
def get_active_link(db: Session, review_id: uuid.UUID) -> ReferralLink | None:
    return db.scalar(select(ReferralLink).where(
        ReferralLink.review_id == review_id,
        ReferralLink.status == ReferralLinkStatus.active))


def list_links(db: Session, review_id: uuid.UUID) -> list[ReferralLink]:
    return list(db.scalars(select(ReferralLink)
                           .where(ReferralLink.review_id == review_id)
                           .order_by(ReferralLink.created_at.desc())))


# --- URL validation (§4) ---
def _platform_blocked(db: Session, product_id: uuid.UUID, platform: Platform) -> bool:
    """True only when an explicit non-monetizable platform row exists (Lazada A6)."""
    return db.scalar(select(ProductPlatform.id).where(
        ProductPlatform.product_id == product_id,
        ProductPlatform.platform == platform,
        ProductPlatform.is_monetizable.is_(False))) is not None


def validate_affiliate_url(db: Session, url: str, platform: Platform,
                           product_id: uuid.UUID) -> None:
    def fail(rule: str) -> AppError:
        return AppError(f"Affiliate URL rejected: {rule}.", code="affiliate_url_invalid",
                        status_code=422, title="Invalid affiliate URL",
                        extra={"rule": rule, "platform": platform.value})

    if not url or len(url) > MAX_URL_LEN:
        raise fail("url_too_long_or_empty")
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise fail("not_https")
    if "@" in (parts.netloc or ""):
        raise fail("userinfo_not_allowed")
    host = (parts.hostname or "").lower()
    if not host:
        raise fail("no_host")
    allowed = settings.affiliate_domains.get(platform.value, [])
    if not any(host == d or host.endswith("." + d) for d in allowed):
        raise fail("domain_not_allowed")
    if _platform_blocked(db, product_id, platform):
        raise fail("platform_not_monetizable")


# --- Moderator actions ---
def attach_link_and_publish(db: Session, review: Review, moderator_id: uuid.UUID,
                            url: str, platform: Platform,
                            sub_id: str | None = None) -> Review:
    if review.star_rating <= 2:
        raise _conflict("<=2-star reviews route to the Honesty Fund; publish without "
                        "a link instead.", "stars_too_low_for_link")
    if review.verification_status != VerificationStatus.verified:
        raise _conflict("Only verified reviews (proof photo) can be monetized.",
                        "review_not_verified")
    if get_active_link(db, review.id) is not None:
        raise _conflict("This review already has an active referral link.",
                        "active_link_exists")
    validate_affiliate_url(db, url, platform, review.product_id)

    # Attribution key (M3 slice 12). Defaults to the review's deterministic
    # sub-ID; a moderator may override it to match what they actually typed into
    # the affiliate dashboard. `sub_id_in_url` records whether the pasted link
    # visibly carries it — a false here means the monthly report will very likely
    # come back unattributable for this link.
    effective_sub_id = (sub_id or sub_id_for_review(review.id)).strip()
    db.add(ReferralLink(review_id=review.id, platform=platform, url=url,
                        status=ReferralLinkStatus.active,
                        sub_id=effective_sub_id,
                        sub_id_in_url=effective_sub_id in url,
                        review_version=review.current_version, created_by=moderator_id))
    review.affiliate_link = url
    review.earn_eligible_status = EarnEligibleStatus.monetized
    if review.published_at is None:
        review.published_at = _now()
        _award_publish_tokens(db, review)
    # M3 slice 10: every monetized review runs a revenue-share contract. A
    # re-attach after a revoke reuses the existing active one (no new term).
    ensure_contract(db, review)
    _audit(db, moderator_id, ModerationAction.affiliate_link_attach, review.id,
           context={"platform": platform.value, "url": url})
    recompute_product_aggregates(db, review.product_id)
    if review.author_id is not None:
        recompute_user_trust(db, review.author_id)  # publish moves trust (slice 3)
    db.commit()
    db.refresh(review)
    return review


def publish_without_link(db: Session, review: Review, moderator_id: uuid.UUID) -> Review:
    if review.published_at is not None:
        raise _conflict("Review is already published.", "already_published")
    # <=2 stars route to the Honesty Fund; others are approved (unmonetized).
    review.earn_eligible_status = (EarnEligibleStatus.honesty_fund if review.star_rating <= 2
                                   else EarnEligibleStatus.approved)
    review.published_at = _now()
    _award_publish_tokens(db, review)
    _audit(db, moderator_id, ModerationAction.publish, review.id,
           context={"routed_to": review.earn_eligible_status.value})
    recompute_product_aggregates(db, review.product_id)
    if review.author_id is not None:
        recompute_user_trust(db, review.author_id)  # publish moves trust (slice 3)
    db.commit()
    db.refresh(review)
    return review


def reject(db: Session, review: Review, moderator_id: uuid.UUID, reason: str) -> Review:
    if review.published_at is not None:
        raise _conflict("Cannot reject a published review; unpublish it instead.",
                        "already_published")
    review.earn_eligible_status = EarnEligibleStatus.rejected
    _audit(db, moderator_id, ModerationAction.reject, review.id, notes=reason)
    if review.author_id is not None:
        recompute_user_trust(db, review.author_id)
    db.commit()
    db.refresh(review)
    return review


def revoke_link(db: Session, review: Review, moderator_id: uuid.UUID, reason: str) -> Review:
    link = get_active_link(db, review.id)
    if link is None:
        raise _conflict("No active referral link to revoke.", "no_active_link")
    link.status = ReferralLinkStatus.revoked
    link.revoked_by = moderator_id
    link.revoked_at = _now()
    link.revoke_reason = reason
    review.affiliate_link = None
    # Content stays published; monetization drops back to approved (link pending).
    review.earn_eligible_status = EarnEligibleStatus.approved
    _audit(db, moderator_id, ModerationAction.affiliate_link_revoke, review.id, notes=reason)
    db.commit()
    db.refresh(review)
    return review


def unpublish(db: Session, review: Review, moderator_id: uuid.UUID,
              reason: str | None = None) -> Review:
    if review.published_at is None:
        raise _conflict("Review is not published.", "not_published")
    previous = review.earn_eligible_status
    review.published_at = None
    # Back into the moderation queue, not into limbo. `get_queue` selects
    # `pending` AND unpublished, so clearing `published_at` while leaving the
    # status at `approved`/`monetized`/`honesty_fund` strands the review: gone
    # from the site *and* absent from the queue, with nothing in the moderator
    # UI that can reach it again. Two reviews were sitting in that state in
    # production when this was found, the older one for eleven days.
    #
    # `pending` is also the honest description of what an unpublished review
    # is - it needs a decision - and it is the one status `reject` and
    # `publish_without_link` both accept, so the moderator who took it down can
    # still act on it afterwards.
    review.earn_eligible_status = EarnEligibleStatus.pending
    _audit(db, moderator_id, ModerationAction.unpublish, review.id, notes=reason,
           context={"previous_status": previous.value})
    recompute_product_aggregates(db, review.product_id)
    if review.author_id is not None:
        recompute_user_trust(db, review.author_id)
    db.commit()
    db.refresh(review)
    return review


# --- Click attribution (§3 GET /r/{id}) ---

# Marketplaces that echo custom sub-IDs back to us on conversion. Lazada does so
# through its postback macros and its /marketing/conversion/report API; Shopee's
# programme has no equivalent, so its links are passed through untouched and
# reconciled from the monthly CSV.
_SUB_ID_PLATFORMS = {Platform.lazada}


def decorate_affiliate_url(url: str, platform: Platform, sub_id: str | None,
                           click_ref: str) -> str:
    """Append our attribution keys to an outbound affiliate URL.

    `sub_id1` carries the review, `sub_id2` the individual click. Without
    `sub_id2` a conversion can only be traced to the review — which is what the
    monthly CSV already gives us — so this is what buys per-click attribution.

    Existing parameters win: if the moderator already typed a `sub_id1` into the
    dashboard when generating the link, theirs is what Lazada has on file and
    overwriting it here would break their reporting. Lazada's own guidance also
    reserves `sub_aff_id` for sub-affiliate channels, so it is never used as a
    click id (their troubleshooting note #4).
    """
    if platform not in _SUB_ID_PLATFORMS:
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if sub_id and not query.get("sub_id1"):
        query["sub_id1"] = sub_id
    if not query.get("sub_id2"):
        query["sub_id2"] = click_ref
    return urlunsplit(parts._replace(query=urlencode(query)))


def record_click(db: Session, review: Review, link: ReferralLink,
                 user_id: uuid.UUID | None, user_agent: str | None,
                 ip_address: str | None) -> str:
    """Create a `sessions` click row with the PII retention schedule; return the
    destination affiliate URL to redirect to."""
    now = _now()
    deadlines = retention_deadlines(now)
    click_ref = f"ref_{uuid.uuid4().hex[:12]}"
    destination = decorate_affiliate_url(link.url, link.platform, link.sub_id, click_ref)
    db.add(ClickSession(
        session_id=f"clk_{uuid.uuid4().hex[:12]}",
        review_id=review.id, product_id=review.product_id, user_id=user_id,
        # Store where the user was actually sent, decoration included — otherwise
        # a support question about a conversion cannot be answered from the row.
        destination_url=destination, platform=link.platform,
        click_ref=click_ref,
        clicked_at=now, user_agent=user_agent, ip_address=ip_address,
        ua_purge_at=deadlines["ua_purge_at"], ip_hash_at=deadlines["ip_hash_at"],
        ip_delete_at=deadlines["ip_delete_at"],
    ))
    db.commit()
    return destination


# --- Moderator queue (§3 GET /admin/review-queue) ---
def get_queue(db: Session, limit: int = 50, offset: int = 0) -> tuple[list[Review], list[Review]]:
    """Return (pending reviews, monetized-but-edited-since reviews)."""
    pending = list(db.scalars(
        select(Review)
        .where(Review.earn_eligible_status == EarnEligibleStatus.pending,
               Review.published_at.is_(None), Review.is_removed.is_(False))
        .order_by(Review.created_at.asc()).limit(limit).offset(offset)))

    edited = list(db.scalars(
        select(Review)
        .join(ReferralLink, ReferralLink.review_id == Review.id)
        .where(Review.earn_eligible_status == EarnEligibleStatus.monetized,
               ReferralLink.status == ReferralLinkStatus.active,
               Review.current_version > ReferralLink.review_version,
               Review.is_removed.is_(False))
        .order_by(Review.updated_at.desc())))
    return pending, edited


# --- Canonical, server-side prioritized queue (design §5) ------------------- #
#
# `get_queue` above is the pre-priority view: pending sorted by age, edited by
# recency, each paged in SQL. It stays for the deprecated `pending` /
# `edited_since_monetized` response arrays. The prioritized queue below loads the
# WHOLE backlog, runs the pure policy evaluator on every candidate, and only then
# orders and pages — so a high-priority review is on page one even when it was
# created after the first fifty.

_QueueKind = Literal["pending", "edited"]

_BASIS_FOR_KIND: dict[_QueueKind, Literal["review_created_at", "review_updated_at"]] = {
    "pending": "review_created_at",
    "edited": "review_updated_at",
}


@dataclass(frozen=True)
class QueueQuery:
    """Server-side filters + paging for the prioritized review queue.

    Ordering is by policy alone (assessment order key, then review id); ``offset``
    only picks which already-ordered slice to return. ``cursor`` is accepted for
    forward compatibility and unused in this slice.
    """

    band: PriorityBand | None = None
    lane: PriorityLane | None = None
    sla: SlaState | None = None
    factor: str | None = None
    q: str | None = None
    limit: int = 50
    offset: int = 0
    cursor: str | None = None


@dataclass(frozen=True)
class _AssessedCard:
    review_id: uuid.UUID
    kind: _QueueKind
    item: QueueItem
    order_key: tuple
    #: The row itself, so a caller aggregating the whole queue (the admin
    #: Overview) can read its columns without re-querying what this pass loaded.
    review: Review
    #: Distinct reports filed against this review. Carried separately from the
    #: assessment because "reported" is its own question: the Overview's
    #: Flagged bar counts reported targets, not High ones.
    report_count: int


@dataclass(frozen=True)
class PrioritizedQueueSnapshot:
    """One evaluation pass shared by the canonical and compatibility views."""

    page: QueuePage
    pending: list[QueueItem]
    edited_since_monetized: list[QueueItem]


_QUERY_CHUNK_SIZE = 500


def _chunks(values: Collection[uuid.UUID]) -> Iterator[tuple[uuid.UUID, ...]]:
    items = tuple(dict.fromkeys(values))
    for start in range(0, len(items), _QUERY_CHUNK_SIZE):
        yield items[start : start + _QUERY_CHUNK_SIZE]


def _ensure_utc(value: datetime) -> datetime:
    """DB timestamps are ``timestamptz`` (aware); coerce any stray naive value to
    UTC so the pure evaluator never rejects a real queue candidate."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def assessment_to_queue_schema(assessment: PriorityAssessment) -> QueuePriorityAssessment:
    """Map the pure-policy dataclass onto the wire schema (design §5). The
    internal ``order_key`` is deliberately not serialized — ordering is the
    server's job, not the client's."""
    return QueuePriorityAssessment(
        policy_version=assessment.policy_version,
        lane=assessment.lane,
        score=assessment.integrity_score,
        band=assessment.band,
        sla_state=assessment.sla_state,
        due_at=assessment.due_at,
        factors=[
            QueuePriorityFactor(
                code=factor.code,
                observed=factor.observed,
                contribution=factor.contribution,
                explanation=factor.explanation,
            )
            for factor in assessment.factors
        ],
    )


def _all_queue_candidates(db: Session) -> list[tuple[Review, _QueueKind]]:
    """Every review currently in the moderator queue, unpaginated.

    Same membership rules as ``get_queue``, without its limit/offset: the
    prioritized queue must see the whole backlog to place work correctly.
    """
    pending = db.scalars(
        select(Review).where(
            Review.earn_eligible_status == EarnEligibleStatus.pending,
            Review.published_at.is_(None),
            Review.is_removed.is_(False),
        ).order_by(Review.created_at.asc())
    ).all()
    edited = db.scalars(
        select(Review)
        .join(ReferralLink, ReferralLink.review_id == Review.id)
        .where(
            Review.earn_eligible_status == EarnEligibleStatus.monetized,
            ReferralLink.status == ReferralLinkStatus.active,
            Review.current_version > ReferralLink.review_version,
            Review.is_removed.is_(False),
        ).order_by(Review.updated_at.desc())
    ).all()
    # Disjoint by construction: `pending` status vs `monetized` status.
    return [(r, "pending") for r in pending] + [(r, "edited") for r in edited]


def _build_assessed_cards(
    db: Session,
    reviews: list[tuple[Review, _QueueKind]],
    *,
    now: datetime | None = None,
) -> list[_AssessedCard]:
    """Build one queue card + priority assessment per (review, kind).

    Product, author, report, and fraud facts are all loaded in bounded batches.
    No fact source performs a query per review.
    """
    evaluated_at = _ensure_utc(now) if now is not None else datetime.now(UTC)
    if not reviews:
        return []

    product_ids = {review.product_id for review, _ in reviews}
    products: dict[uuid.UUID, Product] = {}
    for chunk in _chunks(product_ids):
        products.update(
            (product.id, product)
            for product in db.scalars(
                select(Product)
                .options(selectinload(Product.platforms))
                .where(Product.id.in_(chunk))
            )
        )
    author_ids = {review.author_id for review, _ in reviews if review.author_id}
    authors: dict[uuid.UUID, User] = {}
    for chunk in _chunks(author_ids):
        authors.update(
            (user.id, user)
            for user in db.scalars(select(User).where(User.id.in_(chunk)))
        )

    report_facts = report_service.report_facts_by_target(
        db, ModerationTargetType.review, [review.id for review, _ in reviews]
    )
    signals_by_review = fraud_service.compute_signals_by_review(
        db,
        [review for review, _ in reviews],
        authors,
        now=evaluated_at,
    )

    cards: list[_AssessedCard] = []
    for review, kind in reviews:
        product = products.get(review.product_id)
        author = authors.get(review.author_id) if review.author_id else None
        signals = signals_by_review[review.id]
        edited = kind == "edited"

        # Temporary queue-entry-time approximation (no lifecycle column yet):
        # creation for an initial pending review, last edit for an edited one.
        queued_at = _ensure_utc(
            review.created_at if kind == "pending" else review.updated_at
        )
        facts = report_facts.get(review.id, report_service.NO_REPORTS)
        assessment = evaluate_priority(
            PriorityFacts(
                queued_at=queued_at,
                report_count=facts.count,
                report_reasons=facts.reasons,
                edited_since_monetized=edited,
                velocity=signals["velocity"],
                collusion=signals["collusion"],
                duplicate_content=signals["duplicate_content"],
                manually_escalated=False,
            ),
            now=evaluated_at,
        )

        platforms = list(product.platforms) if product is not None else []
        item = QueueItem(
            review=ReviewOut.model_validate(review),
            product=QueueProduct(
                id=product.id if product is not None else review.product_id,
                canonical_name=product.canonical_name if product is not None else None,
                source_url=product.source_url if product is not None else None,
                platforms=[
                    QueuePlatform(platform=p.platform, is_monetizable=p.is_monetizable)
                    for p in platforms
                ],
            ),
            author=(
                QueueAuthor(
                    id=author.id,
                    display_name=author.display_name,
                    trust_stage=author.trust_stage,
                    reputation_score=author.reputation_score,
                )
                if author is not None
                else None
            ),
            suggested_platform=suggested_platform_from(product, platforms),
            edited_since_monetized=edited,
            signals=QueueSignals(**signals),
            priority=assessment_to_queue_schema(assessment),
            queue_time_basis=_BASIS_FOR_KIND[kind],
            suggested_sub_id=sub_id_for_review(review.id),
        )
        cards.append(
            _AssessedCard(
                review_id=review.id,
                kind=kind,
                item=item,
                order_key=assessment.order_key,
                review=review,
                report_count=facts.count,
            )
        )
    return cards


def _card_matches(card: _AssessedCard, query: QueueQuery) -> bool:
    priority = card.item.priority
    if query.band is not None and priority.band != query.band:
        return False
    if query.lane is not None and priority.lane != query.lane:
        return False
    if query.sla is not None and priority.sla_state != query.sla:
        return False
    if query.factor is not None and query.factor not in {f.code for f in priority.factors}:
        return False
    if query.q and query.q.strip():
        needle = query.q.strip().lower()
        haystack = " ".join(
            part
            for part in (
                card.item.review.title,
                card.item.review.discussion,
                card.item.product.canonical_name,
            )
            if part
        ).lower()
        if needle not in haystack:
            return False
    return True


def _queue_counts(cards: list[_AssessedCard]) -> QueueCounts:
    by_lane = {lane.value: 0 for lane in PriorityLane}
    by_band = {band.value: 0 for band in PriorityBand}
    by_sla = {state.value: 0 for state in SlaState}
    for card in cards:
        priority = card.item.priority
        by_lane[priority.lane.value] += 1
        by_band[priority.band.value] += 1
        by_sla[priority.sla_state.value] += 1
    return QueueCounts(
        total=len(cards), by_lane=by_lane, by_band=by_band, by_sla=by_sla
    )


def _paginate_cards(cards: list[_AssessedCard], query: QueueQuery) -> QueuePage:
    limit = max(1, min(query.limit, 100))
    offset = max(0, query.offset)

    filtered = [card for card in cards if _card_matches(card, query)]
    # Policy order, then review id — a total order, so repeated calls are stable
    # and `offset` is a pure index into an already-correct sequence.
    filtered.sort(key=lambda card: (card.order_key, card.review_id))

    counts = _queue_counts(filtered)
    window = filtered[offset : offset + limit]
    return QueuePage(
        items=[card.item for card in window],
        total=len(filtered),
        next_cursor=None,
        counts=counts,
    )


def get_prioritized_queue(
    db: Session, query: QueueQuery, *, now: datetime | None = None
) -> QueuePage:
    """Evaluate the whole moderator backlog against the priority policy, apply
    server filters, order by policy, then return the requested page (design §5).

    Ordering correctness never depends on ``offset``; ``next_cursor`` is ``None``
    in this compatibility slice.
    """
    return get_prioritized_queue_snapshot(db, query, now=now).page


def get_prioritized_queue_snapshot(
    db: Session, query: QueueQuery, *, now: datetime | None = None
) -> PrioritizedQueueSnapshot:
    """Evaluate once, then derive the canonical page and deprecated split views.

    Candidate loading preserves the old pending/edited ordering. Building the
    compatibility arrays from the same assessed cards avoids recomputing every
    signal and priority merely to serialize the legacy response fields.
    """
    cards = _build_assessed_cards(db, _all_queue_candidates(db), now=now)
    pending = [card.item for card in cards if card.kind == "pending"]
    edited = [card.item for card in cards if card.kind == "edited"]
    return PrioritizedQueueSnapshot(
        page=_paginate_cards(cards, query),
        pending=pending[query.offset : query.offset + query.limit],
        edited_since_monetized=edited,
    )


@dataclass(frozen=True)
class QueueAssessmentSummary:
    """The whole open backlog, assessed once (design §5).

    Exists so the Overview's headline counts and the queue list cannot disagree
    about what is High or what is late: they are the same numbers, from the same
    evaluation, not two implementations of one policy.
    """

    #: Every candidate row, in candidate-loading order.
    reviews: tuple[Review, ...]
    #: Totals by lane, band and SLA state over that whole set.
    counts: QueueCounts
    #: Ids of the candidates carrying at least one report. Reported is not a
    #: band and not a lane the Overview can read off `counts` — a reported
    #: review can sit in any band — so it is carried explicitly.
    reported_review_ids: frozenset[uuid.UUID]

    @property
    def total(self) -> int:
        return self.counts.total

    @property
    def high_priority(self) -> int:
        return self.counts.by_band.get(PriorityBand.high.value, 0)

    @property
    def approaching(self) -> int:
        return self.counts.by_sla.get(SlaState.approaching.value, 0)

    @property
    def overdue(self) -> int:
        return self.counts.by_sla.get(SlaState.overdue.value, 0)


def assess_open_queue(
    db: Session, *, now: datetime | None = None
) -> QueueAssessmentSummary:
    """Assess every open queue candidate against policy v1 and aggregate it.

    The unfiltered, unpaginated counterpart of `get_prioritized_queue`: same
    candidates, same evaluator, no page. Callers that need totals rather than a
    page (the admin Overview) use this instead of paging through the queue.
    """
    cards = _build_assessed_cards(db, _all_queue_candidates(db), now=now)
    return QueueAssessmentSummary(
        reviews=tuple(card.review for card in cards),
        counts=_queue_counts(cards),
        reported_review_ids=frozenset(
            card.review_id for card in cards if card.report_count > 0
        ),
    )


def build_queue_items(
    db: Session,
    reviews: list[tuple[Review, _QueueKind]],
    *,
    now: datetime | None = None,
) -> dict[uuid.UUID, QueueItem]:
    """Queue cards (priority included) keyed by review id, for callers that keep
    their own ordering — i.e. the deprecated pending/edited response arrays."""
    return {
        card.review_id: card.item
        for card in _build_assessed_cards(db, reviews, now=now)
    }


def suggested_platform_from(product: Product | None,
                            platforms: list[ProductPlatform]) -> Platform | None:
    """Best-guess platform from already-loaded rows (no queries): a monetizable
    product_platform, else inferred from the product's source_url host."""
    for p in platforms:
        if p.is_monetizable:
            return p.platform
    src = product.source_url if product else None
    host = (urlsplit(src).hostname or "").lower() if src else ""
    for plat, domains in settings.affiliate_domains.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return Platform(plat)
    return None


def suggested_platform(db: Session, product_id: uuid.UUID) -> Platform | None:
    """Best-guess platform for the moderator: a monetizable product_platform, else
    inferred from the product's source_url host. Thin DB-loading wrapper around
    ``suggested_platform_from`` for callers that only have a product_id."""
    product = db.get(Product, product_id)
    platforms = list(db.scalars(select(ProductPlatform).where(
        ProductPlatform.product_id == product_id)))
    return suggested_platform_from(product, platforms)
