"""Log unexpected errors without logging the data that caused them.

Exception messages are not safe to log here:

* SQLAlchemy appends the statement's bound values ("[parameters: ...]").
* PostgreSQL puts row values in the DETAIL of some errors, e.g.
  "Key (email)=(someone@example.com) already exists".
* Pydantic validation errors quote the offending input.

So an unexpected error is recorded as: a short reference id (also returned to
the client), the exception type, where it was raised (file, line, function),
and, for database errors, the SQLSTATE and the names of the table, column and
constraint involved. Never the message text, never statement parameters.
"""

import logging
import secrets
import traceback

from sqlalchemy.exc import DBAPIError

logger = logging.getLogger("wendy.errors")

# Names of schema objects are safe and useful; values are not.
_SAFE_DIAGNOSTICS = ("sqlstate", "severity", "schema_name", "table_name", "column_name", "constraint_name", "datatype_name")


def new_error_id() -> str:
    return secrets.token_hex(6)


def _frames(exc: BaseException) -> str:
    """Call sites only (file:line function), innermost first. No source lines, no messages.

    Every frame in this application's own code is kept, plus the three
    innermost frames (usually inside a library), so the trail always shows
    which of our functions was running.
    """
    frames = traceback.extract_tb(exc.__traceback__)
    keep = [f for i, f in enumerate(frames) if i >= len(frames) - 3 or "site-packages" not in f.filename]
    return " <- ".join(f"{'/'.join(f.filename.split('/')[-2:])}:{f.lineno} {f.name}" for f in reversed(keep))


def describe_exception(exc: BaseException) -> str:
    """A log-safe description of an exception. See the module docstring."""
    parts = [f"type={type(exc).__module__}.{type(exc).__qualname__}"]
    if isinstance(exc, DBAPIError):
        original = exc.orig
        parts.append(f"db_error={type(original).__qualname__}")
        diagnostics = getattr(original, "diag", None)
        for name in _SAFE_DIAGNOSTICS:
            value = getattr(diagnostics, name, None) if diagnostics is not None else None
            if value is None and name == "sqlstate":
                value = getattr(original, "sqlstate", None)
            if value:
                parts.append(f"{name}={value}")
        if exc.connection_invalidated:
            parts.append("connection_invalidated=true")
    # Chained causes: types only.
    cause = exc.__cause__ or exc.__context__
    if cause is not None and cause is not getattr(exc, "orig", None):
        parts.append(f"caused_by={type(cause).__qualname__}")
    parts.append(f"at={_frames(exc)}")
    return " ".join(parts)


def log_unexpected(exc: BaseException, error_id: str, method: str, path_template: str) -> None:
    """One ERROR line for an unhandled exception. `path_template` is the route
    pattern (e.g. /api/staff/bookings/{booking_id}), not the concrete URL."""
    logger.error("unhandled error id=%s %s %s %s", error_id, method, path_template, describe_exception(exc))
