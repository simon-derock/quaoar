# spec: SPEC-API-03
# the website answers beginner questions from web/primer.json; it must match the python rules exactly
import importlib.util

from tests.meta.test_docstrings import ROOT


def test_the_website_chat_rules_are_generated_from_the_primer() -> None:
    spec = importlib.util.spec_from_file_location(
        "export_primer", ROOT / "scripts" / "export_primer.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    saved = (ROOT / "web" / "primer.json").read_text(encoding="utf-8")
    assert saved == module.export(), "run: uv run python scripts/export_primer.py"
