"""How many days ago a listing was posted (the map's `daysAgo`).

Uses the platform's posting date when present, else the date we first saw it.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional


def _days_between(posted: date, today: date) -> int:
    # Clamp: platforms occasionally report future dates.
    return max((today - posted).days, 0)


def _days_since_first_seen(first_seen_date: Optional[str], today: date) -> int:
    """Days since we first saw the listing (ISO date string), or 0 if unknown."""
    try:
        return _days_between(date.fromisoformat(first_seen_date), today)
    except (ValueError, TypeError):
        return 0


def days_since_posted_nobroker(activation_date_ms, first_seen_date, today: date) -> int:
    """NoBroker: `activationDate` is epoch milliseconds (0/None when missing)."""
    if activation_date_ms and activation_date_ms > 0:
        return _days_between(datetime.fromtimestamp(activation_date_ms / 1000).date(), today)
    return _days_since_first_seen(first_seen_date, today)


def days_since_posted_magicbricks(post_date_iso, first_seen_date, today: date) -> int:
    """MagicBricks: `postDateT` is an ISO datetime string like '2026-04-24T23:45:31.000Z'."""
    if post_date_iso:
        try:
            posted = datetime.fromisoformat(post_date_iso.replace("Z", "+00:00")).date()
            return _days_between(posted, today)
        except (ValueError, TypeError, AttributeError):
            pass
    return _days_since_first_seen(first_seen_date, today)
