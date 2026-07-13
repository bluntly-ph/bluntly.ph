"""Aggregate v1 router. Feature modules register their routers here."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import admin_referral, ai, auth, membership, products, reviews

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router)
api_v1_router.include_router(products.router)
api_v1_router.include_router(reviews.router)
api_v1_router.include_router(admin_referral.router)
api_v1_router.include_router(membership.router)
api_v1_router.include_router(ai.router)
