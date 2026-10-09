# spec: SPEC-GRD-01
from quaoar.domain.findings import Signal, Status
from quaoar.events import Emitter, MemorySink
from quaoar.guard.query import QueryRejectedError
from quaoar.scan import isolated
from tests.fakes import FixedClock


def test_a_refused_search_becomes_a_could_not_check_line_not_a_crash() -> None:
    sink = MemorySink()
    emit = Emitter("s", sink, FixedClock())

    def refuse() -> list[Signal]:
        raise QueryRejectedError("control", "q")

    signals = isolated(emit, "root", "vendor", "ACME Pvt Ltd", refuse)
    assert [s.status for s in signals] == [Status.UNVERIFIED]
    assert signals[0].rule == "VX-02"
    assert "Couldn't check ACME Pvt Ltd" in signals[0].text
    assert any(e.type == "warn" for e in sink.events)


def test_a_check_that_works_passes_through() -> None:
    emit = Emitter("s", MemorySink(), FixedClock())
    assert isolated(emit, "root", "vendor", "ACME", list) == []
