from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy.orm import Session

from ..models import ApiCache


def cached(db: Session, key: str, ttl_hours: float, fn: Callable):
    """Return a fresh cached payload for `key`, else call fn() and store it. None results are not cached."""
    now = datetime.now(timezone.utc)
    row = db.get(ApiCache, key)
    if row and row.payload is not None and now - row.fetched_at < timedelta(hours=ttl_hours):
        return row.payload
    data = fn()
    if data is None:
        return None
    if row:
        row.payload, row.fetched_at = data, now
    else:
        db.add(ApiCache(key=key, payload=data, fetched_at=now))
    db.commit()
    return data
