# spec: SPEC-STY-01
# the codebase talks through short # comments only, so any docstring fails CI
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("src", "tests", "scripts")


def python_files() -> list[Path]:
    return sorted(p for d in SCANNED if (ROOT / d).is_dir() for p in (ROOT / d).rglob("*.py"))


@pytest.mark.parametrize("path", python_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_docstrings(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert docstring_lines(tree) == []


def test_detector_catches_module_class_and_function_docstrings() -> None:
    source = '"m"\nclass A:\n    "c"\n    def f(self):\n        "f"\n        return 1\n'
    assert docstring_lines(ast.parse(source)) == [1, 3, 5]


def test_detector_ignores_plain_string_expressions_later_in_a_body() -> None:
    source = "def f():\n    x = 1\n    'not a docstring'\n    return x\n"
    assert docstring_lines(ast.parse(source)) == []


def docstring_lines(tree: ast.AST) -> list[int]:
    # a docstring is a bare string as the first statement of a module, class or function
    owners = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, owners) or not node.body:
            continue
        first = node.body[0]
        if not isinstance(first, ast.Expr):
            continue
        if isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            lines.append(first.lineno)
    return sorted(lines)
