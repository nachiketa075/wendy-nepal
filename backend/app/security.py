import datetime as dt
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .errors import ApiError
from .models import Owner, OwnerSession

MIN_PASSWORD_LENGTH = 12
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

_hasher = PasswordHasher()
# Verified against when the email is unknown so both paths cost the same.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, owner: Owner) -> tuple[str, OwnerSession]:
    now = dt.datetime.now(dt.UTC)
    db.execute(delete(OwnerSession).where(OwnerSession.expires_at < now))
    token = secrets.token_urlsafe(32)
    session = OwnerSession(
        owner_id=owner.id,
        token_hash=_digest(token),
        csrf_token=secrets.token_urlsafe(32),
        expires_at=now + dt.timedelta(hours=get_settings().session_ttl_hours),
    )
    db.add(session)
    db.commit()
    return token, session


def _load_session(request: Request, db: Session) -> OwnerSession | None:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        return None
    session = db.scalar(select(OwnerSession).where(OwnerSession.token_hash == _digest(token)))
    if session is None or session.expires_at <= dt.datetime.now(dt.UTC) or not session.owner.is_active:
        return None
    return session


def require_owner(request: Request, db: Session = Depends(get_db)) -> OwnerSession:
    """Authenticate the owner session and, for state-changing requests, check CSRF.

    Every /api/owner route and logout depend on this.
    """
    session = _load_session(request, db)
    if session is None:
        raise ApiError(401, "not_authenticated", "Please sign in to continue.")
    if request.method not in SAFE_METHODS:
        sent = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(sent, session.csrf_token):
            raise ApiError(403, "csrf_failed", "Your session could not be verified. Please reload and try again.")
    return session
