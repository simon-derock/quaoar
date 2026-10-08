# time as a port so tests can freeze it; durations come from the monotonic ns counter
import time
from datetime import UTC, datetime
from typing import Protocol


class ClockPort(Protocol):
    def now(self) -> datetime: ...

    def ns(self) -> int: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def ns(self) -> int:
        return time.perf_counter_ns()
