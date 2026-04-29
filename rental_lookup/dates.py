"""Compute daysAgo from platform posting dates, with first_seen fallback."""
from datetime import date, datetime


def compute_days_ago(activation_date_ms, first_seen_date, today):
    """NoBroker: use activationDate (epoch ms), fall back to first_seen (ISO date str)."""
    if activation_date_ms and activation_date_ms > 0:
        posted = datetime.fromtimestamp(activation_date_ms / 1000).date()
        days = (today - posted).days
        return max(days, 0)
    if first_seen_date:
        try:
            return max((today - date.fromisoformat(first_seen_date)).days, 0)
        except (ValueError, TypeError):
            pass
    return 0


def compute_days_ago_mb(post_date_iso, first_seen_date, today):
    """MagicBricks: use postDateT (ISO datetime str), fall back to first_seen."""
    if post_date_iso:
        try:
            posted = datetime.fromisoformat(post_date_iso.replace("Z", "+00:00")).date()
            days = (today - posted).days
            return max(days, 0)
        except (ValueError, TypeError):
            pass
    if first_seen_date:
        try:
            return max((today - date.fromisoformat(first_seen_date)).days, 0)
        except (ValueError, TypeError):
            pass
    return 0
