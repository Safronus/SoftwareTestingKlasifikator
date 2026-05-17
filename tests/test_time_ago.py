"""Testy lidsky čitelného formátování času."""

from __future__ import annotations

from datetime import datetime, timedelta

from softwaretestingklasifikator.config import DATE_FORMAT_PY
from softwaretestingklasifikator.domain.time_ago import format_time_ago


def _now():
    return datetime(2026, 5, 16, 14, 30, 0)


def test_just_now():
    now = _now()
    assert format_time_ago(now - timedelta(seconds=10), now=now) == "před chvílí"


def test_minutes():
    now = _now()
    assert format_time_ago(now - timedelta(minutes=5), now=now) == "před 5 min"


def test_hours():
    now = _now()
    assert format_time_ago(now - timedelta(hours=3), now=now) == "před 3 h"


def test_yesterday():
    now = _now()
    assert format_time_ago(now - timedelta(days=1, hours=2), now=now) == "včera"


def test_few_days():
    now = _now()
    assert format_time_ago(now - timedelta(days=3), now=now) == "před 3 dny"


def test_more_than_week_falls_back_to_date():
    now = _now()
    ts = now - timedelta(days=20)
    expected = ts.strftime(DATE_FORMAT_PY)
    assert format_time_ago(ts, now=now) == expected


def test_future_timestamp_falls_back_to_date():
    """Skok systémového času dozadu — žádný „před -5 min"."""
    now = _now()
    ts = now + timedelta(minutes=10)
    expected = ts.strftime(DATE_FORMAT_PY)
    assert format_time_ago(ts, now=now) == expected
