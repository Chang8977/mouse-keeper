"""Work-hours schedule: when keep-alive should switch itself on and off.

Pure date/time logic with no Win32 and no UI, so it can be reasoned about (and
tested) on its own. The engine only ever asks two questions of it -- "are we
inside the window right now?" and "when does the next one start?" -- and acts on
the *change* of the first answer, which is what leaves room for manual
overrides in between (see Engine._check_schedule).

Days are Python weekdays: Monday = 0 ... Sunday = 6. Times are "HH:MM" strings
in the config file because that is what a person editing it expects to see;
internally everything is minutes since midnight.

A window whose end is earlier than its start runs past midnight (22:00-06:00):
it belongs to the day it *starts* on, so a Friday-night shift still covers the
small hours of Saturday. Start == end means the whole day.
"""

from __future__ import annotations

from datetime import datetime, timedelta

DAY_MINUTES = 24 * 60
#: Step of the -/+ buttons in the panel
STEP_MINUTES = 30

DEFAULT_DAYS = (0, 1, 2, 3, 4)
DEFAULT_START = "09:00"
DEFAULT_END = "18:00"


def parse_hhmm(text, default: str) -> int:
    """'09:30' -> 570. Anything unparseable or out of range falls back to default."""
    for candidate in (text, default):
        try:
            hh, mm = str(candidate).strip().split(":")
            h, m = int(hh), int(mm)
        except (ValueError, AttributeError):
            continue
        if 0 <= h < 24 and 0 <= m < 60:
            return h * 60 + m
    return 0


def fmt_hhmm(minutes: int) -> str:
    minutes %= DAY_MINUTES
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def shift(text: str, delta_minutes: int, default: str) -> str:
    """Move a time by delta, wrapping around midnight."""
    return fmt_hhmm(parse_hhmm(text, default) + delta_minutes)


def clean_days(days) -> list[int]:
    """Validate a weekday list from the config: ints 0-6, no duplicates, sorted."""
    out = set()
    try:
        for d in days:
            if isinstance(d, bool):
                continue
            d = int(d)
            if 0 <= d <= 6:
                out.add(d)
    except (TypeError, ValueError):
        return list(DEFAULT_DAYS)
    return sorted(out)


def in_window(days, start: str, end: str, now: datetime) -> bool:
    s = parse_hhmm(start, DEFAULT_START)
    e = parse_hhmm(end, DEFAULT_END)
    cur = now.hour * 60 + now.minute
    today = now.weekday()
    yesterday = (today - 1) % 7
    if s == e:                      # whole day
        return today in days
    if s < e:                       # same-day window
        return today in days and s <= cur < e
    # Runs past midnight: the evening part belongs to today, the early-morning
    # part to the window that started yesterday.
    return (today in days and cur >= s) or (yesterday in days and cur < e)


def next_start(days, start: str, now: datetime) -> datetime | None:
    """When the next window opens, strictly after ``now``. None if no days are set."""
    if not days:
        return None
    s = parse_hhmm(start, DEFAULT_START)
    base = now.replace(hour=s // 60, minute=s % 60, second=0, microsecond=0)
    for offset in range(8):
        cand = base + timedelta(days=offset)
        if cand > now and cand.weekday() in days:
            return cand
    return None


#: Step of the -/+ buttons of "Pause until"
PAUSE_STEP_MINUTES = 15
DEFAULT_PAUSE_UNTIL = "13:30"


def next_occurrence(hhmm: str, now: datetime) -> datetime:
    """The next time the clock shows ``hhmm``: later today, or tomorrow if that
    moment has already passed (or is right now)."""
    m = parse_hhmm(hhmm, DEFAULT_PAUSE_UNTIL)
    cand = now.replace(hour=m // 60, minute=m % 60, second=0, microsecond=0)
    return cand if cand > now else cand + timedelta(days=1)


def suggest_resume(now: datetime, ahead_minutes: int = 30,
                   step: int = PAUSE_STEP_MINUTES) -> str:
    """A sensible default resume time: at least ``ahead_minutes`` from now,
    rounded up to the step grid (12:07 -> 12:45 with the defaults)."""
    m = now.hour * 60 + now.minute + ahead_minutes
    m = -(-m // step) * step
    return fmt_hhmm(m)


def summarize_days(days, labels: list[str]) -> str:
    """[0,1,2,3,4] -> 'Mo–Fr' using the language's short day labels.

    A single contiguous run collapses into a range; anything else is listed.
    """
    days = sorted(days)
    if not days:
        return ""
    if len(days) == 1:
        return labels[days[0]]
    if days == list(range(days[0], days[-1] + 1)):
        return f"{labels[days[0]]}–{labels[days[-1]]}"
    return " ".join(labels[d] for d in days)
