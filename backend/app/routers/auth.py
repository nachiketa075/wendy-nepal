"""Sign-in for every kind of account, customer registration, profile and password reset.

The three sign-in pages share these endpoints. The role and permissions always
come from the account row; nothing a client sends can raise them.
"""

import datetime as dt
import logging
import secrets

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import activity, email_delivery
from ..config import get_settings
from ..database import get_db
from ..errors import ApiError
from ..models import Account, AccountSession, PasswordResetToken
from ..rate_limit import client_ip, limiter
from ..schemas import (
    AccountOut,
    AuthConfig,
    LoginIn,
    PasswordChange,
    ProfileUpdate,
    RegisterIn,
    ResetConfirm,
    ResetRequest,
)
from ..security import (
    MIN_PASSWORD_LENGTH,
    create_session,
    digest,
    hash_password,
    require_session,
    revoke_sessions,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("wendy.auth")

RESET_REQUESTED = "If that email belongs to an account, a link to choose a new password is on its way."
RESET_UNAVAILABLE = "Password reset by email is not set up yet. Please contact the shop to regain access."


def account_out(account: Account, session: AccountSession) -> AccountOut:
    return AccountOut(
        id=account.id,
        email=account.email,
        full_name=account.full_name,
        phone=account.phone,
        role=account.role,
        permissions=sorted(account.permissions or []) if account.role == "employee" else [],
        csrf_token=session.csrf_token,
    )


def _start_session(db: Session, account: Account, response: Response) -> AccountOut:
    token, session = create_session(db, account)
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/api",
    )
    response.headers["Cache-Control"] = "no-store"
    return account_out(account, session)


def create_reset_token(db: Session, account: Account, purpose: str, ttl: dt.timedelta) -> tuple[str, dt.datetime]:
    """Issue a single-use token (only its hash is stored). Earlier unused tokens are cancelled."""
    now = dt.datetime.now(dt.UTC)
    for old in db.scalars(
        select(PasswordResetToken).where(PasswordResetToken.account_id == account.id, PasswordResetToken.used_at.is_(None))
    ):
        old.used_at = now
    token = secrets.token_urlsafe(32)
    expires_at = now + ttl
    db.add(PasswordResetToken(account_id=account.id, token_hash=digest(token), purpose=purpose, expires_at=expires_at))
    return token, expires_at


def reset_url(token: str) -> str:
    return f"{get_settings().public_site_url.rstrip('/')}/account/reset?token={token}"


@router.get("/config", response_model=AuthConfig)
def auth_config():
    return AuthConfig(password_reset_by_email=email_delivery.delivery_enabled(), min_password_length=MIN_PASSWORD_LENGTH)


@router.post("/register", response_model=AccountOut, status_code=201)
def register(data: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Create a customer account. Always a customer; see RegisterIn."""
    limiter.hit(f"register:ip:{client_ip(request)}", limit=5, window_seconds=60 * 60)
    email = str(data.email).lower()
    if db.scalar(select(Account.id).where(Account.email == email)) is not None:
        raise ApiError(409, "email_taken", "Please check the highlighted details.",
                       {"email": "An account with this email already exists. Try signing in instead."})
    account = Account(email=email, password_hash=hash_password(data.password), role="customer",
                      full_name=data.full_name, phone=data.phone, permissions=[])
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "email_taken", "Please check the highlighted details.",
                       {"email": "An account with this email already exists. Try signing in instead."}) from None
    return _start_session(db, account, response)


@router.post("/login", response_model=AccountOut)
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = data.email.lower()
    limiter.hit(f"login:ip:{client_ip(request)}", limit=20, window_seconds=15 * 60)
    limiter.hit(f"login:email:{email}", limit=5, window_seconds=15 * 60)

    account = db.scalar(select(Account).where(Account.email == email))
    valid = verify_password(data.password, account.password_hash if account else None)
    # A sign-in page only accepts its own kind of account. The answer is the
    # same as for a wrong password, so it reveals nothing about other accounts.
    wrong_portal = account is not None and data.portal is not None and account.role != data.portal
    if not valid or account is None or not account.is_active or wrong_portal:
        raise ApiError(401, "invalid_credentials", "The email or password is not correct.")
    return _start_session(db, account, response)


@router.get("/me", response_model=AccountOut)
def me(response: Response, session: AccountSession = Depends(require_session)):
    response.headers["Cache-Control"] = "no-store"
    return account_out(session.account, session)


@router.post("/logout", status_code=204)
def logout(response: Response, session: AccountSession = Depends(require_session), db: Session = Depends(get_db)):
    db.delete(session)
    db.commit()
    response.delete_cookie(get_settings().session_cookie_name, path="/api")


@router.patch("/profile", response_model=AccountOut)
def update_profile(data: ProfileUpdate, session: AccountSession = Depends(require_session), db: Session = Depends(get_db)):
    """Name and phone only. Email, role and permissions cannot be changed here."""
    account = session.account
    changes = data.model_dump(exclude_unset=True)
    if "full_name" in changes and changes["full_name"] is None:
        raise ApiError(422, "validation_error", "Please check the highlighted details.", {"full_name": "Please enter your name."})
    for field, value in changes.items():
        setattr(account, field, value)
    db.commit()
    return account_out(account, session)


@router.post("/password", status_code=204)
def change_password(data: PasswordChange, request: Request, session: AccountSession = Depends(require_session),
                    db: Session = Depends(get_db)):
    account = session.account
    limiter.hit(f"password:account:{account.id}", limit=5, window_seconds=15 * 60)
    if not verify_password(data.current_password, account.password_hash):
        raise ApiError(422, "validation_error", "Please check the highlighted details.",
                       {"current_password": "That is not your current password."})
    account.password_hash = hash_password(data.new_password)
    revoke_sessions(db, account.id, keep_session_id=session.id)  # sign out everywhere else
    activity.record(db, account, "account.password_changed", "account", account.id)
    db.commit()


@router.post("/password-reset/request", status_code=202)
def request_password_reset(data: ResetRequest, request: Request, db: Session = Depends(get_db)):
    """Always answers the same way, whether or not the email has an account."""
    email = data.email.lower()
    limiter.hit(f"reset:ip:{client_ip(request)}", limit=5, window_seconds=60 * 60)
    limiter.hit(f"reset:email:{email}", limit=3, window_seconds=60 * 60)
    if not email_delivery.delivery_enabled():
        # Nothing can be sent, so say so rather than implying an email is coming.
        return {"email_delivery": False, "message": RESET_UNAVAILABLE}

    account = db.scalar(select(Account).where(Account.email == email, Account.is_active.is_(True)))
    if account is not None:
        ttl = dt.timedelta(minutes=get_settings().password_reset_ttl_minutes)
        token, _ = create_reset_token(db, account, "reset", ttl)
        db.commit()
        sent = email_delivery.send_email(
            account.email,
            "Choose a new password for Wendy Juice Shop",
            f"Hello {account.full_name},\n\nUse this link to choose a new password. It works once and expires in "
            f"{get_settings().password_reset_ttl_minutes} minutes:\n\n{reset_url(token)}\n\n"
            "If you did not ask for this, you can ignore this message.\n",
        )
        if not sent:
            logger.warning("password reset email could not be delivered")
    return {"email_delivery": True, "message": RESET_REQUESTED}


@router.post("/password-reset/confirm", status_code=204)
def confirm_password_reset(data: ResetConfirm, request: Request, db: Session = Depends(get_db)):
    limiter.hit(f"reset-confirm:ip:{client_ip(request)}", limit=10, window_seconds=15 * 60)
    now = dt.datetime.now(dt.UTC)
    record = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == digest(data.token)).with_for_update())
    account = db.get(Account, record.account_id) if record else None
    if record is None or record.used_at is not None or record.expires_at <= now or account is None or not account.is_active:
        db.rollback()
        raise ApiError(400, "invalid_token", "This link is not valid any more. Please ask for a new one.")
    record.used_at = now
    account.password_hash = hash_password(data.new_password)
    revoke_sessions(db, account.id)
    activity.record(db, account, "account.password_set" if record.purpose == "setup" else "account.password_reset", "account", account.id)
    db.commit()
