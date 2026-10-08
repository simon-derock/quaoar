# spec: SPEC-STY-05
# dependencies point from domain outward; an upward import fails CI
import ast
import re
from pathlib import Path

import pytest

from tests.meta.test_docstrings import ROOT

SPEC = ROOT / "PLAN_SPEC.md"
PACKAGE_ROOT = ROOT / "src" / "quaoar"
LAYER = re.compile(r"Layer (\d+): ([^.]+)\.")


def module_files() -> list[Path]:
    return sorted(p for p in PACKAGE_ROOT.rglob("*.py") if p != PACKAGE_ROOT / "__init__.py")


@pytest.mark.parametrize("path", module_files(), ids=lambda p: str(p.relative_to(PACKAGE_ROOT)))
def test_imports_never_point_to_a_higher_layer(path: Path) -> None:
    layers = layer_map()
    own = component(path)
    assert own in layers, f"{own} has no layer in PLAN_SPEC.md"
    upward = [dep for dep in internal_imports(path) if layers.get(dep, 99) > layers[own]]
    assert upward == [], f"{own} (layer {layers[own]}) imports higher layers: {upward}"


def test_layer_list_is_parsed() -> None:
    layers = layer_map()
    assert layers["domain"] == 0
    assert layers["guard"] < layers["serp"] < layers["checks"] < layers["cli"]


def layer_map() -> dict[str, int]:
    found: dict[str, int] = {}
    for level, names in LAYER.findall(SPEC.read_text(encoding="utf-8")):
        for name in re.findall(r"`([a-z_]+)`", names):
            found[name] = int(level)
    return found


def component(path: Path) -> str:
    # quaoar/serp/ledger.py belongs to "serp", quaoar/scan.py to "scan"
    rel = path.relative_to(PACKAGE_ROOT)
    return rel.parts[0] if len(rel.parts) > 1 else rel.stem


def internal_imports(path: Path) -> set[str]:
    deps: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        deps.update(n.split(".")[1] for n in names if n.startswith("quaoar.") and n.count(".") >= 1)
    deps.discard(component(path))
    return deps
