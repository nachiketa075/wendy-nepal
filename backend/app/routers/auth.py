from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..errors import ApiError
from ..models import Owner, OwnerSession
from ..rate_limit import client_ip, limiter
from ..schemas import LoginIn, SessionOut
from ..security import create_session, require_owner, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=SessionOut)
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = data.email.lower()
    limiter.hit(f"login:ip:{client_ip(request)}", limit=10, window_seconds=15 * 60)
    limiter.hit(f"login:email:{email}", limit=5, window_seconds=15 * 60)

    owner = db.scalar(select(Owner).where(func.lower(Owner.email) == email))
    valid = verify_password(data.password, owner.password_hash if owner else None)
    if not valid or owner is None or not owner.is_active:
        raise ApiError(401, "invalid_credentials", "The email or password is not correct.")

    token, session = create_session(db, owner)
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
    return SessionOut(email=owner.email, csrf_token=session.csrf_token)


@router.get("/me", response_model=SessionOut)
def me(response: Response, session: OwnerSession = Depends(require_owner)):
    response.headers["Cache-Control"] = "no-store"
    return SessionOut(email=session.owner.email, csrf_token=session.csrf_token)


@router.post("/logout", status_code=204)
def logout(response: Response, session: OwnerSession = Depends(require_owner), db: Session = Depends(get_db)):
    db.delete(db.merge(session))
    db.commit()
    response.delete_cookie(get_settings().session_cookie_name, path="/api")
