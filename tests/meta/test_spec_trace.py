# spec: SPEC-STY-03
# every test cites a real spec; in strict mode every P0 spec has a test
import os
import re

from tests.meta.test_docstrings import ROOT

SPEC = ROOT / "PLAN_SPEC.md"
DEFINED = re.compile(r"^- (SPEC-[A-Z]+-\d{2}) \[(P\d)\]", re.M)
CITED = re.compile(r"^# spec: (.+)$", re.M)
ID = re.compile(r"SPEC-[A-Z]+-\d{2}")


def test_tests_cite_only_defined_specs() -> None:
    unknown = cited_ids() - set(defined_ids())
    assert unknown == set(), f"tests cite unknown specs: {sorted(unknown)}"


def test_p0_specs_have_tests_in_strict_mode() -> None:
    if os.environ.get("QUAOAR_TRACE_STRICT") != "1":
        return
    missing = {s for s, prio in defined_ids().items() if prio == "P0"} - cited_ids()
    assert missing == set(), f"P0 specs without tests: {sorted(missing)}"


def test_spec_ids_are_unique() -> None:
    ids = DEFINED.findall(SPEC.read_text(encoding="utf-8"))
    names = [i for i, _ in ids]
    assert len(names) == len(set(names))


def defined_ids() -> dict[str, str]:
    return dict(DEFINED.findall(SPEC.read_text(encoding="utf-8")))


def cited_ids() -> set[str]:
    cited: set[str] = set()
    for path in (ROOT / "tests").rglob("test_*.py"):
        for line in CITED.findall(path.read_text(encoding="utf-8")):
            cited.update(ID.findall(line))
    return cited
