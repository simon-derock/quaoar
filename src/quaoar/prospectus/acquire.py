# prospectus intake: a local pdf or one https download, every byte checked before parsing
import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from quaoar.domain.ids import sha256_hex

MAX_BYTES = 40 * 1024 * 1024
TIMEOUT_S = 30.0
MAX_REDIRECTS = 3
ATTEMPTS = 3
PDF_MAGIC = b"%PDF"
# their terms forbid automated collection, so these documents are downloaded by hand
EXCHANGE_HOSTS = ("nseindia.com", "bseindia.com")


class IntakeError(ValueError):
    def __init__(self, rule: str, detail: str = "") -> None:
        super().__init__(f"{rule}: {detail}" if detail else rule)
        self.rule = rule


@dataclass(frozen=True, slots=True)
class Prospectus:
    path: Path
    sha256: str
    size: int
    source: str


def from_path(path: Path, max_bytes: int = MAX_BYTES) -> Prospectus:
    if path.is_symlink():
        raise IntakeError("symlink", "pass the real file")
    if path.suffix.lower() != ".pdf":
        raise IntakeError("suffix", path.suffix)
    if not path.is_file():
        raise IntakeError("missing", str(path))
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise IntakeError("too_large", f"{len(data)} bytes")
    if not data.startswith(PDF_MAGIC):
        raise IntakeError("not_pdf")
    return Prospectus(path, sha256_hex(data), len(data), str(path))


def from_url(
    url: str,
    dest_dir: Path,
    http: httpx.Client,
    resolve: Callable[[str], list[str]] | None = None,
    max_bytes: int = MAX_BYTES,
) -> Prospectus:
    lookup = resolve or resolve_host
    current = url

    # redirects are followed by hand so every hop gets the same checks as the first
    for _ in range(MAX_REDIRECTS + 1):
        check_url(current, lookup)
        fetched = fetch_with_retry(http, current, max_bytes)
        if isinstance(fetched, str):
            current = urljoin(current, fetched)
            continue
        return store(fetched, dest_dir, url)
    raise IntakeError("redirects", f"more than {MAX_REDIRECTS}")


def fetch_with_retry(http: httpx.Client, url: str, max_bytes: int) -> bytes | str:
    # a dropped connection halfway through a 9 MB file is routine; try again before giving up
    last = "no attempt"
    for _ in range(ATTEMPTS):
        try:
            with http.stream("GET", url, timeout=TIMEOUT_S, follow_redirects=False) as response:
                if response.is_redirect:
                    return str(response.headers.get("location", ""))
                if response.status_code >= 400:
                    raise IntakeError("http_status", f"the server answered {response.status_code}")
                return read_capped(response, max_bytes)
        except httpx.TransportError as exc:
            last = type(exc).__name__
    raise IntakeError("download_failed", f"{last} after {ATTEMPTS} tries; download it by hand")


def check_url(url: str, lookup: Callable[[str], list[str]]) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise IntakeError("scheme", parts.scheme)
    if parts.username or parts.password:
        raise IntakeError("credentials")
    host = (parts.hostname or "").lower()
    if any(host == h or host.endswith("." + h) for h in EXCHANGE_HOSTS):
        raise IntakeError("exchange", "download it manually, then pass the file path")

    # every address the name resolves to must be public, or the host is refused
    addresses = lookup(host)
    if not addresses or not all(ipaddress.ip_address(a).is_global for a in addresses):
        raise IntakeError("private_address", host)


def read_capped(response: httpx.Response, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise IntakeError("too_large", f"over {max_bytes} bytes")
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data.startswith(PDF_MAGIC):
        raise IntakeError("not_pdf")
    return data


def store(data: bytes, dest_dir: Path, source: str) -> Prospectus:
    digest = sha256_hex(data)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{digest}.pdf"
    tmp = path.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(path)
    return Prospectus(path, digest, len(data), source)


def resolve_host(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return []
    return sorted({str(info[4][0]) for info in infos})
