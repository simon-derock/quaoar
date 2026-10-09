# spec: SPEC-AG-01, SPEC-AG-03, SPEC-AG-04, SPEC-AG-05, SPEC-AG-06, SPEC-KEY-05
from collections.abc import Mapping
from pathlib import Path

from pydantic import JsonValue, SecretStr
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel

from quaoar.agent.loop import AgentInvestigator, Budget
from quaoar.checks.book import Goal
from quaoar.events import Emitter, MemorySink
from quaoar.llm.client import LlmClient
from quaoar.serp.ledger import Ledger
from tests.fakes import FixedClock, scripted_model
from tests.unit.agent.test_tools import REGISTRY_PAGE, RoutedSearch

KEYS = [SecretStr("cohere-key-one-1234567890"), SecretStr("cohere-key-two-1234567890")]
GOAL = Goal(
    kind="vendor",
    entity="BRIGHTWELL POLYMERS PRIVATE LIMITED",
    known={"city": "Pune"},
    gaps=("registry", "maps"),
    done=('registry: "BRIGHTWELL POLYMERS"',),
    tools=("search_registry", "search_maps"),
)
PLACE: dict[str, JsonValue] = {
    "title": "Brightwell Polymers",
    "type": "Factory",
    "address": "Hinjewadi, Pune",
}


def route(engine: str, params: Mapping[str, object]) -> dict[str, JsonValue]:
    if engine == "google_maps":
        return {"local_results": [PLACE]} if "Pune" in str(params["q"]) else {}
    return {"organic_results": [dict(REGISTRY_PAGE)]}


def llm(tmp_path: Path, factory) -> tuple[LlmClient, MemorySink]:  # type: ignore[no-untyped-def]
    sink, clock = MemorySink(), FixedClock()
    client = LlmClient(
        ledger=Ledger(tmp_path), clock=clock, model_name="command-a-03-2025",
        keys=KEYS, factory=factory, emit=Emitter("s", sink, clock), sleep=lambda _: None,
    )  # fmt: skip
    return client, sink


def investigator(tmp_path: Path, factory, budget: Budget | None = None):  # type: ignore[no-untyped-def]
    client, sink = llm(tmp_path, factory)
    search = RoutedSearch(route)
    return AgentInvestigator(client, search, Emitter("s", sink, FixedClock()), budget), search, sink


STEPS: list[tuple[str, dict[str, object]]] = [
    ("search_maps", {"terms": "Brightwell Polymers", "why": "maps gap, words alone"}),
    (
        "search_maps",
        {"terms": "Brightwell Polymers Pune", "why": "maps gap, name plus the registry city"},
    ),
]
FINAL = {"resolved": ["maps"], "unresolved": ["registry"], "note": "Maps listing found in Pune."}


def test_the_loop_reasons_with_tools_then_hands_over_evidence(tmp_path: Path) -> None:
    inv, search, _ = investigator(tmp_path, lambda m, k: scripted_model(STEPS, FINAL))
    book = inv.run(GOAL)
    assert [c.tool for c in book.calls] == ["search_maps", "search_maps"]
    assert [c.why for c in book.calls][1].startswith("maps gap")
    assert len(search.calls) == 2
    assert [h.item["title"] for h in book.of("search_maps")] == ["Brightwell Polymers"]
    assert book.handoff is not None
    assert book.handoff.resolved == ["maps"]


def test_a_finished_investigation_is_replayed_from_its_trace_without_a_model(
    tmp_path: Path,
) -> None:
    first, _, _ = investigator(tmp_path, lambda m, k: scripted_model(STEPS, FINAL))
    first.run(GOAL)

    def forbidden(model: str, key: str) -> Model:
        raise AssertionError("the model must not be called on replay")

    second, search, sink = investigator(tmp_path, forbidden)
    book = second.run(GOAL)
    assert [c.tool for c in book.calls] == ["search_maps", "search_maps"]
    assert book.handoff is not None
    assert book.handoff.note == "Maps listing found in Pune."
    assert len(search.calls) == 2
    assert not [e for e in sink.events if e.type == "llm"]


def test_an_agent_that_never_finishes_is_stopped_and_keeps_what_it_found(tmp_path: Path) -> None:
    endless = [
        ("search_maps", {"terms": f"Brightwell Pune {n}", "why": "again"}) for n in range(30)
    ]
    inv, search, _ = investigator(tmp_path, lambda m, k: scripted_model(endless), Budget(6, 3))
    book = inv.run(GOAL)
    assert book.handoff is None
    assert len(search.calls) <= 3
    assert len(book.of("search_maps")) >= 1


def test_the_model_cannot_set_a_status_only_a_handoff(tmp_path: Path) -> None:
    sneaky = {"resolved": ["maps"], "unresolved": [], "note": "ok", "status": "consistent"}
    inv, _, _ = investigator(tmp_path, lambda m, k: scripted_model([], sneaky))
    book = inv.run(GOAL)
    assert book.handoff is not None
    assert not hasattr(book.handoff, "status")


def test_a_rate_limited_key_hands_the_investigation_to_the_next_key(tmp_path: Path) -> None:
    seen: list[str] = []

    def factory(model: str, key: str) -> Model:
        seen.append(key)
        if key == KEYS[0].get_secret_value():

            def limited(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
                raise ModelHTTPError(429, model)

            return FunctionModel(limited)
        return scripted_model(STEPS, FINAL)

    inv, _, _ = investigator(tmp_path, factory)
    book = inv.run(GOAL)
    assert seen[0] == KEYS[0].get_secret_value()
    assert KEYS[1].get_secret_value() in seen
    assert book.handoff is not None


def test_with_every_key_failing_the_book_is_simply_empty(tmp_path: Path) -> None:
    def factory(model: str, key: str) -> Model:
        def down(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            raise ModelHTTPError(429, model)

        return FunctionModel(down)

    inv, _, _ = investigator(tmp_path, factory)
    book = inv.run(GOAL)
    assert book.hits == []
    assert book.handoff is None
