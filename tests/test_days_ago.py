"""Tests for days_ago computation: platform date first, first_seen as fallback."""
from datetime import date, datetime


def compute_days_ago(activation_date_ms, first_seen_date, today):
    from rental_lookup.dates import compute_days_ago as _fn
    return _fn(activation_date_ms, first_seen_date, today)


def compute_days_ago_mb(post_date_iso, first_seen_date, today):
    from rental_lookup.dates import compute_days_ago_mb as _fn
    return _fn(post_date_iso, first_seen_date, today)


# --- NoBroker (activationDate is epoch ms) ---

def test_nb_uses_activation_date():
    """Should use NoBroker's activationDate when available."""
    # April 20, 2026 in epoch ms
    apr20 = int(datetime(2026, 4, 20).timestamp() * 1000)
    today = date(2026, 4, 29)
    result = compute_days_ago(apr20, None, today)
    assert result == 9


def test_nb_falls_back_to_first_seen():
    """When activationDate is 0 or missing, use first_seen."""
    today = date(2026, 4, 29)
    result = compute_days_ago(0, "2026-04-25", today)
    assert result == 4


def test_nb_activation_date_zero_with_no_first_seen():
    """When both are missing, return 0 (new today)."""
    today = date(2026, 4, 29)
    result = compute_days_ago(0, None, today)
    assert result == 0


def test_nb_activation_date_none():
    today = date(2026, 4, 29)
    result = compute_days_ago(None, "2026-04-27", today)
    assert result == 2


def test_nb_very_old_activation_date():
    """A listing from 2020 should show correct large daysAgo."""
    old = int(datetime(2020, 1, 1).timestamp() * 1000)
    today = date(2026, 4, 29)
    result = compute_days_ago(old, None, today)
    assert result > 2000


def test_nb_future_activation_date_clamps_to_zero():
    """If activationDate is in the future (data error), clamp to 0."""
    future = int(datetime(2026, 5, 10).timestamp() * 1000)
    today = date(2026, 4, 29)
    result = compute_days_ago(future, None, today)
    assert result == 0


# --- MagicBricks (postDateT is ISO string) ---

def test_mb_uses_post_date():
    today = date(2026, 4, 29)
    result = compute_days_ago_mb("2026-04-24T23:45:31.000Z", None, today)
    assert result == 5


def test_mb_falls_back_to_first_seen():
    today = date(2026, 4, 29)
    result = compute_days_ago_mb("", "2026-04-26", today)
    assert result == 3


def test_mb_none_post_date():
    today = date(2026, 4, 29)
    result = compute_days_ago_mb(None, "2026-04-28", today)
    assert result == 1


def test_mb_both_missing():
    today = date(2026, 4, 29)
    result = compute_days_ago_mb(None, None, today)
    assert result == 0
