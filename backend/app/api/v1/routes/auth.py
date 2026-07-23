"""Auth routes (M1) — register, login (OAuth2 password flow), me."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AuthError
from app.core.rate_limit import auth_rate_limiter
from app.core.security import create_access_token, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    OtpRequestIn,
    OtpVerifyIn,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.schemas.common import Problem
from app.services.auth_service import authenticate_user, register_user
from app.services.otp_service import issue_otp, verify_otp

router = APIRouter(prefix="/auth", tags=["auth"])

_PROBLEM = {401: {"model": Problem}, 409: {"model": Problem}, 429: {"model": Problem}}


def _token_response(user: User) -> TokenResponse:
    token = create_access_token(user.id, user.role.value)
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=201,
             responses=_PROBLEM, summary="Register a new account")
def register(payload: RegisterRequest, db: Session = Depends(get_db),
             _: None = Depends(auth_rate_limiter("register"))) -> TokenResponse:
    user = register_user(db, payload)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse, responses=_PROBLEM,
             summary="Log in (OAuth2 password flow; username = email)")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db),
          _: None = Depends(auth_rate_limiter("login"))) -> TokenResponse:
    user = authenticate_user(db, form.username, form.password)
    if user is None:
        raise AuthError("Invalid email or password.", code="invalid_credentials")
    if user.is_suspended:
        raise AuthError("Account is suspended.", code="account_suspended", status_code=403)
    return _token_response(user)


@router.post("/otp/request", status_code=202, responses=_PROBLEM,
             summary="Request a one-time login/signup code by email")
def otp_request(payload: OtpRequestIn, db: Session = Depends(get_db),
                _: None = Depends(auth_rate_limiter("otp_request"))) -> dict[str, str]:
    # Always 202, whether or not the address has an account — anything else turns
    # this endpoint into a user-enumeration oracle.
    issue_otp(db, payload.email, payload.purpose)
    return {"status": "sent"}


@router.post("/otp/verify", response_model=TokenResponse, responses=_PROBLEM,
             summary="Exchange a one-time code for an access token")
def otp_verify(payload: OtpVerifyIn, db: Session = Depends(get_db),
               _: None = Depends(auth_rate_limiter("otp_verify"))) -> TokenResponse:
    user = verify_otp(db, payload.email, payload.code)
    if user.is_suspended:
        raise AuthError("Account is suspended.", code="account_suspended",
                        status_code=403)
    return _token_response(user)


@router.get("/me", response_model=UserOut, responses=_PROBLEM,
            summary="Current authenticated user")
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
