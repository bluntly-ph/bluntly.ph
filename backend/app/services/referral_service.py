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
from datetime import UTC, datetime
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

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
from app.services.contract_service import ensure_contract
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
    review.published_at = None
    _audit(db, moderator_id, ModerationAction.unpublish, review.id, notes=reason)
    recompute_product_aggregates(db, review.product_id)
    if review.author_id is not None:
        recompute_user_trust(db, review.author_id)
    db.commit()
    db.refresh(review)
    return review


# --- Click attribution (§3 GET /r/{id}) ---
def record_click(db: Session, review: Review, link: ReferralLink,
                 user_id: uuid.UUID | None, user_agent: str | None,
                 ip_address: str | None) -> str:
    """Create a `sessions` click row with the PII retention schedule; return the
    destination affiliate URL to redirect to."""
    now = _now()
    deadlines = retention_deadlines(now)
    db.add(ClickSession(
        session_id=f"clk_{uuid.uuid4().hex[:12]}",
        review_id=review.id, product_id=review.product_id, user_id=user_id,
        destination_url=link.url, platform=link.platform,
        click_ref=f"ref_{uuid.uuid4().hex[:12]}",
        clicked_at=now, user_agent=user_agent, ip_address=ip_address,
        ua_purge_at=deadlines["ua_purge_at"], ip_hash_at=deadlines["ip_hash_at"],
        ip_delete_at=deadlines["ip_delete_at"],
    ))
    db.commit()
    return link.url


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
