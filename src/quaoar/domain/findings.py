# what checks observe and what rules conclude; statuses only ever come from rules
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class Status(StrEnum):
    CONSISTENT = "consistent"
    INCONSISTENT = "inconsistent"
    UNVERIFIED = "unverified"
    NOT_APPLICABLE = "not_applicable"


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    engine: str
    request: str = Field(description="first 16 hex of the request hash")
    search_id: str | None
    url: str
    title: str
    snippet: str = Field(max_length=300)
    published: date | None = None


class Observation(BaseModel):
    model_config = ConfigDict(frozen=True)

    check: str
    subject: str
    key: str
    value: JsonValue
    evidence: tuple[Evidence, ...] = ()
    page: int | None = None


class Signal(BaseModel):
    model_config = ConfigDict(frozen=True)

    check: str
    rule: str
    subject: str
    status: Status
    text: str
    observed: str = ""
    threshold: str = ""
    page: int | None = None
    evidence: tuple[Evidence, ...] = ()
    pit_ok: bool = False
