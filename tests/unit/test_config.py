# spec: SPEC-KEY-01, SPEC-KEY-05
from pathlib import Path

from quaoar.config import all_secrets, load_settings


def write_env(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def test_reads_comma_separated_key_lists_from_the_env_file(tmp_path: Path) -> None:
    env = write_env(tmp_path, "# keys\nSERPAPI_API_KEYS=aaa, bbb ,\nCOHERE_API_KEYS='c1,c2'\n")
    settings = load_settings({}, env)
    assert [k.get_secret_value() for k in settings.serpapi_keys] == ["aaa", "bbb"]
    assert [k.get_secret_value() for k in settings.cohere_keys] == ["c1", "c2"]


def test_single_key_names_are_a_fallback(tmp_path: Path) -> None:
    settings = load_settings({"SERPAPI_API_KEY": "solo", "COHERE_API_KEY": "one"}, None)
    assert [k.get_secret_value() for k in settings.serpapi_keys] == ["solo"]
    assert [k.get_secret_value() for k in settings.cohere_keys] == ["one"]


def test_process_environment_beats_the_file(tmp_path: Path) -> None:
    env = write_env(tmp_path, "QUAOAR_MAX_CREDITS_PER_SCAN=45\n")
    assert load_settings({"QUAOAR_MAX_CREDITS_PER_SCAN": "12"}, env).max_credits_per_scan == 12


def test_defaults_and_home_expansion() -> None:
    settings = load_settings({"QUAOAR_HOME": "~/.qtest"}, None)
    assert settings.home == Path("~/.qtest").expanduser()
    assert settings.cohere_model == "command-a-plus-05-2026"
    assert settings.key_reserve == 5


def test_keys_never_show_up_in_repr_or_str() -> None:
    settings = load_settings({"SERPAPI_API_KEYS": "topsecretvalue123"}, None)
    assert "topsecretvalue123" not in repr(settings)
    assert "topsecretvalue123" not in str(settings)
    assert all_secrets(settings) == ["topsecretvalue123"]
