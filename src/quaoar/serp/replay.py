# replay bundles: recorded, sanitized responses keyed by request hash; no network, no keys
import json
from pathlib import Path

from quaoar.serp.ledger import BlobStore


class ReplayMissError(LookupError):
    pass


class ReplayStore:
    def __init__(self, root: Path) -> None:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self._requests: dict[str, str] = manifest["requests"]
        self._blobs = BlobStore(root / "blobs")

    def get(self, request_hash: str) -> bytes:
        digest = self._requests.get(request_hash)
        if digest is None:
            raise ReplayMissError(request_hash)
        return self._blobs.get(digest)


def write_bundle(root: Path, bodies: dict[str, bytes]) -> None:
    blobs = BlobStore(root / "blobs")
    requests = {request_hash: blobs.put(body) for request_hash, body in sorted(bodies.items())}
    manifest = {"version": 1, "requests": requests}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
