import datetime as dt
import hashlib
import hmac
import secrets
from collections.abc import Callable

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .errors import ApiError
from .models import Account, AccountSession

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


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, account: Account) -> tuple[str, AccountSession]:
    now = dt.datetime.now(dt.UTC)
    db.execute(delete(AccountSession).where(AccountSession.expires_at < now))
    token = secrets.token_urlsafe(32)
    session = AccountSession(
        account_id=account.id,
        token_hash=digest(token),
        csrf_token=secrets.token_urlsafe(32),
        expires_at=now + dt.timedelta(hours=get_settings().session_ttl_hours),
    )
    db.add(session)
    db.commit()
    return token, session


def revoke_sessions(db: Session, account_id: int, keep_session_id: int | None = None) -> None:
    statement = delete(AccountSession).where(AccountSession.account_id == account_id)
    if keep_session_id is not None:
        statement = statement.where(AccountSession.id != keep_session_id)
    db.execute(statement)


def _load_session(request: Request, db: Session) -> AccountSession | None:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        return None
    session = db.scalar(select(AccountSession).where(AccountSession.token_hash == digest(token)))
    # The account row is read fresh on every request, so deactivation and
    # permission changes apply to the very next call without a new sign-in.
    if session is None or session.expires_at <= dt.datetime.now(dt.UTC) or not session.account.is_active:
        return None
    return session


def require_session(request: Request, db: Session = Depends(get_db)) -> AccountSession:
    """Authenticate the session cookie and, for state-changing requests, check CSRF."""
    session = _load_session(request, db)
    if session is None:
        raise ApiError(401, "not_authenticated", "Please sign in to continue.")
    if request.method not in SAFE_METHODS:
        sent = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(sent, session.csrf_token):
            raise ApiError(403, "csrf_failed", "Your session could not be verified. Please reload and try again.")
    return session


def require_account(session: AccountSession = Depends(require_session)) -> Account:
    return session.account


def _forbidden() -> ApiError:
    return ApiError(403, "forbidden", "You don't have permission to do that.")


def require_role(*roles: str) -> Callable[..., Account]:
    """Dependency: the signed-in account must have one of these roles.

    The role comes from the account row, never from the request.
    """

    def dependency(account: Account = Depends(require_account)) -> Account:
        if account.role not in roles:
            raise _forbidden()
        return account

    return dependency


require_owner = require_role("owner")
require_customer = require_role("customer")
require_staff = require_role("owner", "employee")


def require_permission(permission: str) -> Callable[..., Account]:
    """Dependency: owner, or an employee the owner has granted this permission."""

    def dependency(account: Account = Depends(require_staff)) -> Account:
        if not account.can(permission):
            raise _forbidden()
        return account

    return dependency


def ensure(account: Account, permission: str) -> None:
    if not account.can(permission):
        raise _forbidden()
