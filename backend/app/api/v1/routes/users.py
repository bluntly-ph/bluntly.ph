"""User trust profile + moderator role management (M2 slices 3-4)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import AppError, NotFoundError
from app.core.rate_limit import enforce_rate_limit
from app.core.security import get_current_user, get_optional_user, require_role
from app.db.session import get_db
from app.models.enums import MemberRole, ModerationAction, ModerationTargetType
from app.models.moderation import ModerationLog
from app.models.user import User, UserBadge
from app.schemas.auth import ProfileUpdateIn, UserOut
from app.schemas.common import Problem
from app.schemas.user import BadgeOut, RoleUpdate, UserTrustOut
from app.services import contribution_streak, dashboard_service
from app.services.storage import delete_avatar_object, upload_avatar
from app.services.username import MAX_LENGTH, MIN_LENGTH, is_valid_username

router = APIRouter(prefix="/users", tags=["users"])

_AVATAR_PROBLEM = {401: {"model": Problem}, 413: {"model": Problem},
                   415: {"model": Problem}}


def _user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.", code="user_not_found")
    return user


class UsernameAvailability(BaseModel):
    username: str
    available: bool
    reason: str | None = None


# Registered before the `/{user_id}/...` routes so the literal segment is never
# considered as a UUID path parameter.
@router.get("/username-available", response_model=UsernameAvailability,
            summary="Whether a username is free to claim")
def username_available(request: Request, username: str,
                       db: Session = Depends(get_db),
                       user: User | None = Depends(get_optional_user),
                       ) -> UsernameAvailability:
    """Check a username *before* the signup wizard is finished (BUG-018).

    Availability was only ever discovered on submit, so someone could pick a
    handle, choose interests, read two more screens, and only then be told to
    start over with a different name.

    No enumeration concern: usernames are public handles, printed on every
    review and profile. Rate-limited anyway, because a cheap endpoint that
    answers questions about accounts should not be free to hammer.
    """
    enforce_rate_limit(request, "username-check", max_requests=60)
    candidate = (username or "").strip()
    # Same rule the write path enforces (services/username.py, mirrored in SQL by
    # migration 0016) rather than a second copy that could drift from it.
    if len(candidate) < MIN_LENGTH:
        return UsernameAvailability(
            username=candidate, available=False,
            reason=f"Usernames need at least {MIN_LENGTH} characters.")
    if len(candidate) > MAX_LENGTH:
        return UsernameAvailability(
            username=candidate, available=False,
            reason=f"Usernames are {MAX_LENGTH} characters at most.")
    if not is_valid_username(candidate):
        return UsernameAvailability(
            username=candidate, available=False,
            reason="Lowercase letters, numbers, and underscores only.")
    stmt = select(User.id).where(func.lower(User.username) == candidate.lower())
    # Your own current handle is "available" to you — otherwise the wizard would
    # flag the auto-generated name it prefilled for you as taken.
    if user is not None:
        stmt = stmt.where(User.id != user.id)
    if db.scalar(stmt) is not None:
        return UsernameAvailability(username=candidate, available=False,
                                    reason="That username is already taken.")
    return UsernameAvailability(username=candidate, available=True)


@router.patch("/me", response_model=UserOut,
              responses={401: {"model": Problem}, 409: {"model": Problem}},
              summary="Update the current user's profile")
def update_me(payload: ProfileUpdateIn, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)) -> UserOut:
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.interests is not None:
        # De-duplicate while preserving pick order — the feed reads it as a
        # priority list, not a set.
        user.interests = list(dict.fromkeys(payload.interests))
    if payload.username is not None and payload.username != user.username:
        clash = db.scalar(select(User.id).where(
            func.lower(User.username) == payload.username.lower(),
            User.id != user.id))
        if clash is not None:
            raise AppError("That username is already taken.",
                           code="username_taken", status_code=409,
                           title="Username already registered")
        user.username = payload.username
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/me/avatar", response_model=UserOut, responses=_AVATAR_PROBLEM,
             summary="Upload or replace the current user's avatar")
def set_avatar(file: UploadFile, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)) -> UserOut:
    data = file.file.read()
    new_url = upload_avatar(user.id, data)
    previous = user.avatar_url
    user.avatar_url = new_url
    db.commit()
    db.refresh(user)
    # Only drop the old object once the new one is committed — a failure here
    # must never leave the user with no avatar at all.
    if previous:
        delete_avatar_object(previous)
    return UserOut.model_validate(user)


@router.delete("/me/avatar", status_code=204, responses=_AVATAR_PROBLEM,
               # response_model=None: without it FastAPI infers a model from the
               # `-> None` annotation, which a 204 may not carry.
               response_model=None, summary="Remove the current user's avatar")
def clear_avatar(db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)) -> None:
    previous = user.avatar_url
    user.avatar_url = None
    db.commit()
    if previous:
        delete_avatar_object(previous)


@router.get("/{user_id}/trust", response_model=UserTrustOut,
            summary="Public trust profile (stage, reputation, badges)")
def get_trust(user_id: uuid.UUID, db: Session = Depends(get_db)) -> UserTrustOut:
    user = _user_or_404(db, user_id)
    user_badges = db.scalars(
        select(UserBadge).where(UserBadge.user_id == user.id)
        .options(joinedload(UserBadge.badge))
        .order_by(UserBadge.awarded_at)
    ).all()
    return UserTrustOut(
        id=user.id,
        trust_stage=user.trust_stage,
        trust_level_name=user.trust_level_name,
        reputation_score=user.reputation_score,
        verified_review_count=user.verified_review_count,
        helpfulness_ratio=user.helpfulness_ratio,
        badges=[BadgeOut(badge_id=ub.badge.badge_id, name=ub.badge.name,
                         awarded_at=ub.awarded_at) for ub in user_badges],
    )


@router.patch("/{user_id}/role", response_model=UserOut,
              summary="Promote/demote seller (moderator only)")
def set_role(user_id: uuid.UUID, payload: RoleUpdate, db: Session = Depends(get_db),
             moderator: User = Depends(require_role("moderator"))) -> UserOut:
    if payload.role == MemberRole.moderator:
        raise AppError("The moderator role cannot be granted via the API.",
                       code="role_not_grantable", status_code=422,
                       title="Invalid role")
    user = _user_or_404(db, user_id)
    old_role = user.role
    user.role = payload.role
    db.add(ModerationLog(
        log_id=f"mlog_{uuid.uuid4().hex[:10]}",
        target_type=ModerationTargetType.user, target_ref=user.id,
        moderator_id=moderator.id, action=ModerationAction.override,
        notes="role change",
        context={"from": old_role.value, "to": payload.role.value},
    ))
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


class DashboardSeriesPoint(BaseModel):
    day: date
    #: String-decimal, like every other money field in this API.
    amount: str


class DashboardReviewRow(BaseModel):
    review_id: uuid.UUID
    title: str
    photo_url: str | None
    earnings: str
    views: int
    helped: int
    series: list[DashboardSeriesPoint]


class DashboardSummaryOut(BaseModel):
    range: str
    window_start: date
    window_end: date
    estimated_commission: str
    earned_in_window: str
    total_views: int
    #: Null today — nothing measures read time, and starting to would be
    #: reader-behaviour tracking rather than aggregate counting. Listed in
    #: `unavailable` so the client renders the tile honestly instead of
    #: substituting a plausible number.
    average_read_seconds: int | None
    unavailable: list[str]
    has_earnings: bool
    series: list[DashboardSeriesPoint]
    reviews: list[DashboardReviewRow]


@router.get("/me/dashboard", response_model=DashboardSummaryOut,
            summary="Earnings, views and ranked reviews for the signed-in user")
def my_dashboard(
    range: str = Query(default=dashboard_service.DEFAULT_RANGE),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> DashboardSummaryOut:
    """The contributor dashboard, for the caller and nobody else.

    There is no user id in the path on purpose: a reviewer's earnings are
    theirs alone, and an endpoint that accepts an id is an endpoint someone
    will eventually pass a different id to.
    """
    if range not in dashboard_service.RANGES:
        raise HTTPException(
            status_code=422,
            detail=f"range must be one of {sorted(dashboard_service.RANGES)}")

    result = dashboard_service.summary(db, me.id, range_key=range)
    return DashboardSummaryOut(
        range=result.range_key,
        window_start=result.window_start, window_end=result.window_end,
        estimated_commission=str(result.estimated_commission),
        earned_in_window=str(result.earned_in_window),
        total_views=result.total_views,
        average_read_seconds=result.average_read_seconds,
        unavailable=list(result.unavailable),
        has_earnings=result.has_earnings,
        series=[DashboardSeriesPoint(day=p.day, amount=str(p.amount))
                for p in result.series],
        reviews=[
            DashboardReviewRow(
                review_id=r.review_id, title=r.title, photo_url=r.photo_url,
                earnings=str(r.earnings), views=r.views, helped=r.helped,
                series=[DashboardSeriesPoint(day=p.day, amount=str(p.amount))
                        for p in r.series],
            )
            for r in result.reviews
        ],
    )


class EarningBreakdownOut(BaseModel):
    """What the History frame reveals when a row is expanded."""

    gross_amount: str
    #: Provider commission rate where the import recorded one; null otherwise.
    #: Never derived by dividing, because the two are rounded independently.
    commission_rate: str | None
    platform_share: str
    honesty_fund_share: str
    reviewer_share: str


class EarningRowOut(BaseModel):
    commission_id: str
    occurred_on: date
    review_id: uuid.UUID | None
    review_title: str | None
    product_name: str | None
    photo_url: str | None
    amount: str
    #: pending | to_earn | paid | returned — the reviewer-facing reading of the
    #: canonical lifecycle/settlement pair, never a substitute for either.
    status: str
    breakdown: EarningBreakdownOut


class EarningsHistoryOut(BaseModel):
    all_time: str
    counts: dict[str, int]
    rows: list[EarningRowOut]
    has_data: bool


@router.get("/me/earnings", response_model=EarningsHistoryOut,
            summary="The signed-in reviewer's own earnings history")
def my_earnings(
    status: str = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> EarningsHistoryOut:
    """Earnings for the caller and nobody else.

    No user id in the path, for the same reason as the dashboard: an endpoint
    that accepts one is an endpoint someone will eventually pass a different
    one to.
    """
    if status not in dashboard_service.EARNING_FILTERS:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of {sorted(dashboard_service.EARNING_FILTERS)}")

    result = dashboard_service.earnings_history(db, me.id, status=status, limit=limit)
    return EarningsHistoryOut(
        all_time=str(result.all_time),
        counts=result.counts,
        has_data=result.has_data,
        rows=[
            EarningRowOut(
                commission_id=r.commission_id, occurred_on=r.occurred_on,
                review_id=r.review_id, review_title=r.review_title,
                product_name=r.product_name, photo_url=r.photo_url,
                amount=str(r.amount), status=r.status,
                breakdown=EarningBreakdownOut(
                    gross_amount=str(r.gross_amount),
                    commission_rate=(str(r.commission_rate)
                                     if r.commission_rate is not None else None),
                    platform_share=str(r.platform_share),
                    honesty_fund_share=str(r.honesty_fund_share),
                    reviewer_share=str(r.reviewer_share),
                ),
            )
            for r in result.rows
        ],
    )


class StreakDayOut(BaseModel):
    day: date
    contributed: bool


class ContributionStreakOut(BaseModel):
    current_streak: int
    last_contribution: date | None
    active_today: bool
    total_days: int
    calendar_month: date
    calendar: list[StreakDayOut]


@router.get("/me/streak", response_model=ContributionStreakOut,
            summary="The signed-in reviewer's contribution streak and calendar")
def my_streak(
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
) -> ContributionStreakOut:
    """Days the caller contributed — never days they visited.

    Owner decision, 2026-08-27: this is a contribution streak. It is derived
    entirely from timestamps the application already stores (published reviews,
    questions, answers, price observations), so nothing here tracks reading or
    browsing, and no new telemetry was added to build it.

    No user id in the path, for the same reason as the dashboard and earnings.
    """
    result = contribution_streak.insights_streak(db, me.id)
    return ContributionStreakOut(
        current_streak=result.current_streak,
        last_contribution=result.last_contribution,
        active_today=result.active_today,
        total_days=result.total_days,
        calendar_month=result.calendar_month,
        calendar=[
            StreakDayOut(day=c.day, contributed=c.contributed)
            for c in result.calendar
        ],
    )
