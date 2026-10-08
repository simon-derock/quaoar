# test doubles shared across suites: a clock that only moves when told to
from datetime import UTC, datetime, timedelta


class FixedClock:
    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
        self._ns = 0

    def now(self) -> datetime:
        return self._now

    def ns(self) -> int:
        self._ns += 1_000
        return self._ns

    def advance(self, **delta: float) -> None:
        self._now += timedelta(**delta)
