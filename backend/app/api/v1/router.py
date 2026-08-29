"""Aggregate v1 router. Feature modules register their routers here."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import (
    admin_analytics,
    admin_console,
    admin_earnings,
    admin_referral,
    admin_reports,
    ai,
    auth,
    comments,
    contracts,
    internal_cron,
    membership,
    payouts,
    postback,
    products,
    qa,
    requests,
    reviews,
    tokens,
    traffic_ingest,
    users,
)

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router)
api_v1_router.include_router(products.router)
api_v1_router.include_router(reviews.router)
# After reviews: its paths are literal ("/reviews/{id}/comments") rather than a
# prefix, so registration order decides nothing, but reading order should follow
# the resource they hang off.
api_v1_router.include_router(comments.router)
api_v1_router.include_router(admin_referral.router)
api_v1_router.include_router(admin_earnings.router)
api_v1_router.include_router(admin_analytics.router)
api_v1_router.include_router(admin_console.router)
api_v1_router.include_router(internal_cron.router)
api_v1_router.include_router(traffic_ingest.router)
api_v1_router.include_router(admin_reports.router)
api_v1_router.include_router(membership.router)
api_v1_router.include_router(ai.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(qa.router)
api_v1_router.include_router(tokens.router)
api_v1_router.include_router(requests.router)
api_v1_router.include_router(contracts.router)
api_v1_router.include_router(payouts.router)
api_v1_router.include_router(postback.router)
