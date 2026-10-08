# spec: SPEC-STY-02
# packages in src/quaoar must be components the UML diagram names
import os
import re

from tests.meta.test_docstrings import ROOT

SPEC = ROOT / "PLAN_SPEC.md"
PACKAGE_ROOT = ROOT / "src" / "quaoar"
LIST_LINE = re.compile(r"^Packages under .*SPEC-STY-02 checks this list\): (?P<names>.+)$", re.M)


def test_every_package_is_in_the_uml_list() -> None:
    declared = uml_packages()
    present = code_packages()
    assert present <= declared, f"not in the UML list: {sorted(present - declared)}"
    if os.environ.get("QUAOAR_TRACE_STRICT") == "1":
        assert present == declared, f"in UML but not built: {sorted(declared - present)}"


def test_uml_list_is_parsed() -> None:
    assert {"domain", "guard", "serp"} <= uml_packages()


def uml_packages() -> set[str]:
    match = LIST_LINE.search(SPEC.read_text(encoding="utf-8"))
    assert match is not None, "UML package line missing from PLAN_SPEC.md"
    return set(re.findall(r"`([a-z_]+)`", match.group("names")))


def code_packages() -> set[str]:
    return {p.parent.name for p in PACKAGE_ROOT.glob("*/__init__.py")}
