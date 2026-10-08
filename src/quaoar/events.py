# one event shape for CLI, API, web and the journal; parent links rebuild the causal chain
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, JsonValue

from quaoar.clock import ClockPort

EventType = Literal["stage", "serp", "llm", "guard", "claim", "signal", "card", "warn", "done"]
MAX_EVENT_BYTES = 4096


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    v: int = 1
    id: str
    parent: str | None
    scan: str
    t_ns: int
    type: EventType
    data: dict[str, JsonValue]


class EventTooLargeError(ValueError):
    pass


class EventSink(Protocol):
    def write(self, event: Event) -> None: ...


class MemorySink:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def write(self, event: Event) -> None:
        self.events.append(event)


class JournalSink:
    # append-only, flushed per event, so a killed scan keeps everything it already did
    def __init__(self, path: Path, *, fresh: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        # a re-run of the same scan starts its own journal instead of mixing two runs
        if fresh:
            path.write_text("", encoding="utf-8")

    def write(self, event: Event) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")
            handle.flush()


class Emitter:
    def __init__(
        self,
        scan: str,
        sink: EventSink,
        clock: ClockPort,
        scrub: Callable[[str], str] | None = None,
    ) -> None:
        self._scan, self._sink, self._clock = scan, sink, clock
        self._scrub = scrub or (lambda text: text)
        self._seq = 0

    def __call__(
        self, type_: EventType, data: dict[str, JsonValue], parent: str | None = None
    ) -> str:
        self._seq += 1
        event = Event(
            id=f"{self._scan}-{self._seq:06d}",
            parent=parent,
            scan=self._scan,
            t_ns=self._clock.ns(),
            type=type_,
            data={k: scrubbed(v, self._scrub) for k, v in data.items()},
        )
        if len(event.model_dump_json()) > MAX_EVENT_BYTES:
            raise EventTooLargeError(f"{type_} event over {MAX_EVENT_BYTES} bytes; store a blob")
        self._sink.write(event)
        return event.id


def scrubbed(value: JsonValue, scrub: Callable[[str], str]) -> JsonValue:
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, list):
        return [scrubbed(v, scrub) for v in value]
    if isinstance(value, dict):
        return {k: scrubbed(v, scrub) for k, v in value.items()}
    return value
