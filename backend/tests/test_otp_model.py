"""email_otps table shape."""

from __future__ import annotations

from app.models.enums import OtpPurpose
from app.models.otp import EmailOtp


def test_purpose_enum_members():
    assert {m.value for m in OtpPurpose} == {"signup", "login"}


def test_table_columns():
    cols = set(EmailOtp.__table__.columns.keys())
    assert cols == {
        "id", "email", "code_hash", "purpose", "attempts",
        "expires_at", "consumed_at", "created_at",
    }


def test_code_is_never_stored_plaintext():
    # A `code` column would mean plaintext storage; only the hash may exist.
    assert "code" not in EmailOtp.__table__.columns


def test_email_is_not_foreign_keyed_to_users():
    """A signup code is issued before the user row exists."""
    assert not EmailOtp.__table__.columns["email"].foreign_keys
