# spec: SPEC-STY-04
# short functions keep the block-by-block style readable
import ast
from pathlib import Path

import pytest

from tests.meta.test_docstrings import ROOT, python_files

MAX_LINES = 60


@pytest.mark.parametrize("path", python_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_functions_stay_short(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert long_functions(tree) == []


def test_detector_reports_a_long_function() -> None:
    body = "\n".join("    x = 1" for _ in range(MAX_LINES))
    source = f"def f():\n{body}\n"
    assert long_functions(ast.parse(source)) == [("f", MAX_LINES + 1)]


def long_functions(tree: ast.AST) -> list[tuple[str, int]]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > MAX_LINES:
                found.append((node.name, length))
    return found
