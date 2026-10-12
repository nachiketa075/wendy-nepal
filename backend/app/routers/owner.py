"""Owner-only API: employees, their permissions and sessions, and the activity log.

Employees can never reach these routes, so they cannot create accounts, grant
permissions or change their own privileges."""

import datetime as dt

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import activity
from ..config import get_settings
from ..database import get_db
from ..errors import ApiError
from ..models import Account, AccountSession, ActivityLog
from ..permissions import PERMISSIONS
from ..schemas import ActivityList, EmployeeCreate, EmployeeCreated, EmployeeOut, EmployeeUpdate
from ..security import require_owner, revoke_sessions
from .auth import create_reset_token, reset_url

router = APIRouter(prefix="/api/owner", tags=["owner"], dependencies=[Depends(require_owner)])


def _employee_out(db: Session, account: Account) -> EmployeeOut:
    sessions = db.scalar(
        select(func.count()).select_from(AccountSession)
        .where(AccountSession.account_id == account.id, AccountSession.expires_at > dt.datetime.now(dt.UTC))
    )
    return EmployeeOut(id=account.id, email=account.email, full_name=account.full_name, is_active=account.is_active,
                       permissions=sorted(account.permissions or []), has_password=account.password_hash is not None,
                       active_sessions=sessions, created_at=account.created_at)


def _get_employee(db: Session, employee_id: int) -> Account:
    account = db.scalar(select(Account).where(Account.id == employee_id, Account.role == "employee"))
    if account is None:
        raise ApiError(404, "not_found", "That employee does not exist.")
    return account


def _setup(db: Session, account: Account) -> tuple[str, dt.datetime]:
    token, expires_at = create_reset_token(db, account, "setup", dt.timedelta(hours=get_settings().employee_setup_ttl_hours))
    return reset_url(token), expires_at


@router.get("/permissions")
def list_permissions() -> list[dict]:
    return [{"key": key, "label": label} for key, label in PERMISSIONS.items()]


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees(response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    rows = db.scalars(select(Account).where(Account.role == "employee").order_by(Account.full_name, Account.id)).all()
    return [_employee_out(db, a) for a in rows]


@router.post("/employees", response_model=EmployeeCreated, status_code=201)
def create_employee(data: EmployeeCreate, response: Response, owner: Account = Depends(require_owner),
                    db: Session = Depends(get_db)):
    """Create an employee with no password and the permissions given (none by default).

    The reply carries a one-time setup link for the owner to pass on; no email is sent.
    """
    response.headers["Cache-Control"] = "no-store"
    email = str(data.email).lower()
    if db.scalar(select(Account.id).where(Account.email == email)) is not None:
        raise ApiError(409, "email_taken", "Please check the highlighted details.",
                       {"email": "An account with this email already exists."})
    account = Account(email=email, password_hash=None, role="employee", full_name=data.full_name,
                      permissions=sorted(set(data.permissions)))
    db.add(account)
    db.flush()
    url, expires_at = _setup(db, account)
    activity.record(db, owner, "employee.created", "account", account.id, email=email, permissions=account.permissions)
    db.commit()
    return EmployeeCreated(employee=_employee_out(db, account), setup_url=url, setup_expires_at=expires_at)


@router.post("/employees/{employee_id}/setup-link", response_model=EmployeeCreated)
def new_setup_link(employee_id: int, response: Response, owner: Account = Depends(require_owner), db: Session = Depends(get_db)):
    """Issue a fresh one-time link (cancels earlier ones). Also signs the employee out."""
    response.headers["Cache-Control"] = "no-store"
    account = _get_employee(db, employee_id)
    if not account.is_active:
        raise ApiError(409, "inactive", "Reactivate this employee before sending a new link.")
    url, expires_at = _setup(db, account)
    revoke_sessions(db, account.id)
    activity.record(db, owner, "employee.setup_link_issued", "account", account.id)
    db.commit()
    return EmployeeCreated(employee=_employee_out(db, account), setup_url=url, setup_expires_at=expires_at)


@router.patch("/employees/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: int, data: EmployeeUpdate, owner: Account = Depends(require_owner),
                    db: Session = Depends(get_db)):
    account = _get_employee(db, employee_id)
    changes = data.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise ApiError(422, "validation_error", "Fields cannot be empty.")
    if "permissions" in changes:
        before = sorted(account.permissions or [])
        account.permissions = sorted(set(changes["permissions"]))
        activity.record(db, owner, "employee.permissions_changed", "account", account.id, before=before, after=account.permissions)
    if "full_name" in changes:
        account.full_name = changes["full_name"]
    if "is_active" in changes and changes["is_active"] != account.is_active:
        account.is_active = changes["is_active"]
        if not account.is_active:
            revoke_sessions(db, account.id)
        activity.record(db, owner, "employee.reactivated" if account.is_active else "employee.deactivated", "account", account.id)
    db.commit()
    return _employee_out(db, account)


@router.post("/employees/{employee_id}/revoke-sessions", response_model=EmployeeOut)
def revoke_employee_sessions(employee_id: int, owner: Account = Depends(require_owner), db: Session = Depends(get_db)):
    account = _get_employee(db, employee_id)
    revoke_sessions(db, account.id)
    activity.record(db, owner, "employee.sessions_revoked", "account", account.id)
    db.commit()
    return _employee_out(db, account)


@router.get("/activity", response_model=ActivityList)
def activity_log(response: Response, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                 actor_id: int | None = None, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    conditions = [ActivityLog.actor_id == actor_id] if actor_id else []
    total = db.scalar(select(func.count()).select_from(ActivityLog).where(*conditions))
    rows = db.scalars(select(ActivityLog).where(*conditions).order_by(ActivityLog.id.desc()).limit(limit).offset(offset)).all()
    return ActivityList(items=rows, total=total)
