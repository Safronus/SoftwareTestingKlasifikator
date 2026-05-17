"""Lidsky čitelná česká formulace času „před …"."""

from __future__ import annotations

from datetime import datetime

from softwaretestingklasifikator.config import DATE_FORMAT_PY


def format_time_ago(ts: datetime, *, now: datetime | None = None) -> str:
    """Vrátí např. „před chvílí", „před 5 min", „před 2 h", „včera",
    nebo absolutní datum pro vzdálenější časy."""
    now = now or datetime.now()
    delta = now - ts
    secs = int(delta.total_seconds())

    if secs < 0:
        # Časový skok dozadu (změna systémového času) — fallback na datum.
        return ts.strftime(DATE_FORMAT_PY)
    if secs < 60:
        return "před chvílí"
    if secs < 3600:
        mins = secs // 60
        return f"před {mins} min"
    if secs < 86_400:
        hrs = secs // 3600
        # 1 h, 2–4 h, 5+ h — necháváme jednotku stejnou („h"), bez gramatiky.
        return f"před {hrs} h"
    days = secs // 86_400
    if days == 1:
        return "včera"
    if days < 7:
        return f"před {days} dny"
    # Týden a více — ukaž rovnou datum (přehlednější než „před 23 dny").
    return ts.strftime(DATE_FORMAT_PY)
