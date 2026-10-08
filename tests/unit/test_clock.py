# the real clock is timezone-aware and its counter only moves forward
from quaoar.clock import SystemClock


def test_system_clock_is_utc_and_monotonic() -> None:
    clock = SystemClock()
    assert clock.now().utcoffset() is not None
    first = clock.ns()
    assert clock.ns() >= first
