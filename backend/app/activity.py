from sqlalchemy.orm import Session

from .models import Account, ActivityLog


def record(db: Session, actor: Account | None, action: str, target_type: str | None = None,
           target_id: object = None, **detail) -> None:
    """Add an activity-log entry to the current transaction (caller commits)."""
    db.add(
        ActivityLog(
            actor_id=actor.id if actor else None,
            actor_role=actor.role if actor else "system",
            actor_label=f"{actor.full_name} ({actor.email})" if actor else "System",
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            detail=detail,
        )
    )
