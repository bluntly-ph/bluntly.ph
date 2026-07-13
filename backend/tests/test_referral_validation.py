"""URL validation matrix for referral links (M2 slice 1)."""

from __future__ import annotations

import uuid

import pytest

from app.core.errors import AppError
from app.models.enums import Platform
from app.services.referral_service import validate_affiliate_url
from tests.conftest import requires_db


@requires_db
def test_url_validation_matrix():
    from app.db.session import SessionLocal
    db = SessionLocal()
    pid = uuid.uuid4()  # no product_platforms rows -> not blocked
    try:
        # Valid links per platform (no raise).
        validate_affiliate_url(db, "https://shopee.ph/x-i.1.2", Platform.shopee, pid)
        validate_affiliate_url(db, "https://s.shopee.ph/abc", Platform.shopee, pid)  # subdomain
        validate_affiliate_url(db, "https://amzn.to/abc", Platform.amazon, pid)
        validate_affiliate_url(db, "https://c.lazada.com.ph/x", Platform.lazada, pid)

        def rule_of(url: str, platform: Platform) -> str:
            with pytest.raises(AppError) as exc:
                validate_affiliate_url(db, url, platform, pid)
            assert exc.value.status_code == 422
            assert exc.value.code == "affiliate_url_invalid"
            return exc.value.extra["rule"]

        assert rule_of("http://shopee.ph/x", Platform.shopee) == "not_https"
        assert rule_of("https://user:pw@shopee.ph/x", Platform.shopee) == "userinfo_not_allowed"
        assert rule_of("https://evil.example.com/x", Platform.shopee) == "domain_not_allowed"
        # Right URL, wrong declared platform.
        assert rule_of("https://shopee.ph/x", Platform.amazon) == "domain_not_allowed"
        # 'other' platform has no allowlist.
        assert rule_of("https://shopee.ph/x", Platform.other) == "domain_not_allowed"
        long_url = "https://shopee.ph/" + "a" * 2100
        assert rule_of(long_url, Platform.shopee) == "url_too_long_or_empty"
    finally:
        db.close()
