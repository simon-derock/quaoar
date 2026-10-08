# settings from the process environment and an optional .env file; keys stay SecretStr
import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, SecretStr


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    serpapi_keys: tuple[SecretStr, ...] = ()
    cohere_keys: tuple[SecretStr, ...] = ()
    cohere_model: str = "command-a-plus-05-2026"
    home: Path = Path("~/.quaoar").expanduser()
    max_credits_per_scan: int = 45
    key_reserve: int = 5
    cors_origin: str = ""


def load_settings(
    environ: Mapping[str, str] | None = None, env_file: Path | None = None
) -> Settings:
    # the real environment wins over the file, so CI and shells can override anything
    values = read_env_file(env_file) if env_file is not None and env_file.is_file() else {}
    values.update(os.environ if environ is None else environ)

    return Settings(
        serpapi_keys=split_keys(
            values.get("SERPAPI_API_KEYS") or values.get("SERPAPI_API_KEY", "")
        ),
        cohere_keys=split_keys(values.get("COHERE_API_KEYS") or values.get("COHERE_API_KEY", "")),
        cohere_model=values.get("COHERE_MODEL") or Settings().cohere_model,
        home=Path(values.get("QUAOAR_HOME", "~/.quaoar")).expanduser(),
        max_credits_per_scan=int(values.get("QUAOAR_MAX_CREDITS_PER_SCAN", "45")),
        key_reserve=int(values.get("QUAOAR_KEY_RESERVE", "5")),
        cors_origin=values.get("QUAOAR_CORS_ORIGIN", ""),
    )


def all_secrets(settings: Settings) -> list[str]:
    return [k.get_secret_value() for k in (*settings.serpapi_keys, *settings.cohere_keys)]


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, raw = line.partition("=")
        values[name.strip()] = raw.strip().strip("'\"")
    return values


def split_keys(raw: str) -> tuple[SecretStr, ...]:
    return tuple(SecretStr(part.strip()) for part in raw.split(",") if part.strip())
