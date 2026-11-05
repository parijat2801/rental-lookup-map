"""Listing age (daysAgo): platform posting date first, first_seen as fallback."""
from datetime import date, datetime

from rental_lookup.listing_age import (
    days_since_posted_acres99, days_since_posted_magicbricks, days_since_posted_nobroker,
)


# --- NoBroker (activationDate is epoch ms) ---

def test_nobroker_uses_activation_date():
    """Should use NoBroker's activationDate when available."""
    # April 20, 2026 in epoch ms
    apr20 = int(datetime(2026, 4, 20).timestamp() * 1000)
    today = date(2026, 4, 29)
    result = days_since_posted_nobroker(apr20, None, today)
    assert result == 9


def test_nobroker_falls_back_to_first_seen():
    """When activationDate is 0 or missing, use first_seen."""
    today = date(2026, 4, 29)
    result = days_since_posted_nobroker(0, "2026-04-25", today)
    assert result == 4


def test_nobroker_activation_date_zero_with_no_first_seen():
    """When both are missing, return 0 (new today)."""
    today = date(2026, 4, 29)
    result = days_since_posted_nobroker(0, None, today)
    assert result == 0


def test_nobroker_activation_date_none():
    today = date(2026, 4, 29)
    result = days_since_posted_nobroker(None, "2026-04-27", today)
    assert result == 2


def test_nobroker_very_old_activation_date():
    """A listing from 2020 should show correct large daysAgo."""
    old = int(datetime(2020, 1, 1).timestamp() * 1000)
    today = date(2026, 4, 29)
    result = days_since_posted_nobroker(old, None, today)
    assert result > 2000


def test_nobroker_future_activation_date_clamps_to_zero():
    """If activationDate is in the future (data error), clamp to 0."""
    future = int(datetime(2026, 5, 10).timestamp() * 1000)
    today = date(2026, 4, 29)
    result = days_since_posted_nobroker(future, None, today)
    assert result == 0


# --- MagicBricks (postDateT is ISO string) ---

def test_magicbricks_uses_post_date():
    today = date(2026, 4, 29)
    result = days_since_posted_magicbricks("2026-04-24T23:45:31.000Z", None, today)
    assert result == 5


def test_magicbricks_falls_back_to_first_seen():
    today = date(2026, 4, 29)
    result = days_since_posted_magicbricks("", "2026-04-26", today)
    assert result == 3


def test_magicbricks_none_post_date():
    today = date(2026, 4, 29)
    result = days_since_posted_magicbricks(None, "2026-04-28", today)
    assert result == 1


def test_magicbricks_both_missing():
    today = date(2026, 4, 29)
    result = days_since_posted_magicbricks(None, None, today)
    assert result == 0


# --- 99acres (POSTING_DATE is epoch ms) ---

def test_acres99_uses_posting_date():
    today = date(2026, 4, 29)
    posted = int(datetime(2026, 4, 20).timestamp() * 1000)
    result = days_since_posted_acres99(posted, None, today)
    assert result == 9


def test_acres99_falls_back_to_first_seen():
    today = date(2026, 4, 29)
    result = days_since_posted_acres99(0, "2026-04-25", today)
    assert result == 4


def test_acres99_string_posting_date():
    today = date(2026, 4, 29)
    posted = str(int(datetime(2026, 4, 27).timestamp() * 1000))
    result = days_since_posted_acres99(posted, None, today)
    assert result == 2
