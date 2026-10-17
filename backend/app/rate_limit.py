"""Rate limiting backed by PostgreSQL.

Counters live in the `rate_limit_events` table, so a limit holds across every
API worker and instance that shares the database. Keys (which contain an IP
address or an email) are stored only as SHA-256 digests.
"""

import hashlib
import math
import random

from fastapi import Request
from sqlalchemy import text

from .config import get_settings
from .database import engine
from .errors import ApiError


class RateLimiter:
    def hit(self, key: str, limit: int, window_seconds: int) -> None:
        digest = hashlib.sha256(key.encode()).hexdigest()
        retry_after = None
        with engine.begin() as conn:
            # Serialise concurrent hits on the same key so the count is exact.
            conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": digest})
            conn.execute(
                text("DELETE FROM rate_limit_events WHERE key_hash = :k AND created_at <= now() - make_interval(secs => :w)"),
                {"k": digest, "w": window_seconds},
            )
            count, oldest_age = conn.execute(
                text("SELECT count(*), COALESCE(EXTRACT(EPOCH FROM now() - min(created_at)), 0) FROM rate_limit_events WHERE key_hash = :k"),
                {"k": digest},
            ).one()
            if count >= limit:
                retry_after = max(1, math.ceil(window_seconds - float(oldest_age)))
            else:
                conn.execute(text("INSERT INTO rate_limit_events (key_hash) VALUES (:k)"), {"k": digest})
        if random.random() < 0.01:
            # Occasional housekeeping for keys that are never hit again.
            self.purge_expired()
        if retry_after is not None:
            raise ApiError(
                429,
                "rate_limited",
                "Too many attempts. Please wait a little and try again.",
                headers={"Retry-After": str(retry_after)},
            )

    def reset(self) -> None:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE rate_limit_events"))

    def purge_expired(self, older_than_seconds: int = 2 * 24 * 60 * 60) -> None:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM rate_limit_events WHERE created_at <= now() - make_interval(secs => :w)"),
                {"w": older_than_seconds},
            )


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    if get_settings().trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"
