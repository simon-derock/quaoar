# stable ids: equal content always hashes to the same short id
import hashlib
import json

ID_HEX_LENGTH = 16


def stable_id(value: object) -> str:
    return sha256_hex(canonical_json(value))[:ID_HEX_LENGTH]


def canonical_json(value: object) -> str:
    # sorted keys and no spaces, so equal content always serializes byte for byte the same
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: str | bytes) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()
