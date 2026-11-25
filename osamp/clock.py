"""A clock the tests can move.

This draft does not decide a trusted time source. Callers pass the time.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("time values need a timezone")
    return parsed.astimezone(timezone.utc)


def format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


class Clock:
    def __init__(self, start: str = "2026-11-24T00:00:00+00:00"):
        self._now = parse_time(start)

    def now(self) -> str:
        return format_time(self._now)

    def advance(self, seconds: int) -> str:
        if seconds < 0:
            raise ValueError("time only moves forward in this draft")
        self._now += timedelta(seconds=seconds)
        return self.now()
