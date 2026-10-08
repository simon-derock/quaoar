# spec: SPEC-PDF-01, SPEC-PDF-03, SPEC-SAF-11, SPEC-SAF-12
import ipaddress
from pathlib import Path

import httpx
import pytest

from quaoar.prospectus.acquire import IntakeError, from_path, from_url, resolve_host

PDF = b"%PDF-1.4\n" + b"x" * 200


def public(host: str) -> list[str]:
    return {"files.example.com": ["93.184.216.34"], "cdn.example.com": ["93.184.216.35"]}.get(
        host, ["10.0.0.7"]
    )


def client(handler: httpx.MockTransport | None = None) -> httpx.Client:
    return httpx.Client(
        transport=handler or httpx.MockTransport(lambda _: httpx.Response(200, content=PDF))
    )


def test_downloads_a_pdf_named_by_its_hash(tmp_path: Path) -> None:
    got = from_url("https://files.example.com/a.pdf", tmp_path, client(), resolve=public)
    assert got.path == tmp_path / f"{got.sha256}.pdf"
    assert got.path.read_bytes() == PDF
    assert (got.size, got.source) == (len(PDF), "https://files.example.com/a.pdf")


@pytest.mark.parametrize(
    ("url", "rule"),
    [
        ("http://files.example.com/a.pdf", "scheme"),
        ("https://user:pw@files.example.com/a.pdf", "credentials"),
        ("https://www.nseindia.com/x.pdf", "exchange"),
        ("https://nsearchives.nseindia.com/x.pdf", "exchange"),
        ("https://www.bseindia.com/x.pdf", "exchange"),
        ("https://internal.example.com/a.pdf", "private_address"),
    ],
)
def test_refuses_unsafe_urls_before_any_request(url: str, rule: str, tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=PDF)

    transport = httpx.MockTransport(handler)
    with pytest.raises(IntakeError) as caught:
        from_url(url, tmp_path, client(transport), resolve=public)
    assert caught.value.rule == rule
    assert seen == []


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "169.254.169.254", "192.168.1.5", "::1", "fd00::1"]
)
def test_every_non_public_address_is_refused(address: str, tmp_path: Path) -> None:
    with pytest.raises(IntakeError):
        from_url("https://files.example.com/a.pdf", tmp_path, client(), resolve=lambda _: [address])


def test_redirects_are_followed_by_hand_and_rechecked(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "files.example.com":
            return httpx.Response(302, headers={"location": "https://cdn.example.com/b.pdf"})
        return httpx.Response(200, content=PDF)

    got = from_url(
        "https://files.example.com/a.pdf",
        tmp_path,
        client(httpx.MockTransport(handler)),
        resolve=public,
    )
    assert got.path.read_bytes() == PDF


def test_redirect_into_a_private_network_is_refused(tmp_path: Path) -> None:
    redirect = httpx.MockTransport(
        lambda _: httpx.Response(302, headers={"location": "https://internal.example.com/meta"})
    )
    with pytest.raises(IntakeError) as caught:
        from_url("https://files.example.com/a.pdf", tmp_path, client(redirect), resolve=public)
    assert caught.value.rule == "private_address"


def test_redirect_loops_stop(tmp_path: Path) -> None:
    loop = httpx.MockTransport(
        lambda _: httpx.Response(302, headers={"location": "https://files.example.com/a.pdf"})
    )
    with pytest.raises(IntakeError) as caught:
        from_url("https://files.example.com/a.pdf", tmp_path, client(loop), resolve=public)
    assert caught.value.rule == "redirects"


def test_non_pdf_and_oversized_bodies_are_refused(tmp_path: Path) -> None:
    html = httpx.MockTransport(lambda _: httpx.Response(200, content=b"<html>login</html>"))
    with pytest.raises(IntakeError) as caught:
        from_url("https://files.example.com/a.pdf", tmp_path, client(html), resolve=public)
    assert caught.value.rule == "not_pdf"
    with pytest.raises(IntakeError) as caught:
        from_url(
            "https://files.example.com/a.pdf", tmp_path, client(), resolve=public, max_bytes=100
        )
    assert caught.value.rule == "too_large"
    assert list(tmp_path.glob("*.pdf")) == []


def test_local_pdf_is_hashed_and_checked(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    path.write_bytes(PDF)
    got = from_path(path)
    assert (got.size, got.source) == (len(PDF), str(path))
    assert from_path(path).sha256 == got.sha256


@pytest.mark.parametrize("case", ["missing", "suffix", "symlink", "magic"])
def test_local_path_guard(case: str, tmp_path: Path) -> None:
    real = tmp_path / "real.pdf"
    real.write_bytes(PDF)
    target = {
        "missing": tmp_path / "nope.pdf",
        "suffix": tmp_path / "doc.txt",
        "symlink": tmp_path / "link.pdf",
        "magic": tmp_path / "fake.pdf",
    }[case]
    if case == "suffix":
        target.write_bytes(PDF)
    if case == "symlink":
        target.symlink_to(real)
    if case == "magic":
        target.write_bytes(b"MZ not a pdf")
    with pytest.raises(IntakeError):
        from_path(target)


def test_real_resolver_sees_loopback_and_unknown_hosts() -> None:
    assert all(ipaddress.ip_address(a).is_loopback for a in resolve_host("localhost"))
    assert resolve_host("no-such-host.invalid") == []
