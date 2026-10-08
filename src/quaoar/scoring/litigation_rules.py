# litigation rule: a legal-site matter naming the issuer or a promoter that the prospectus does not list
from datetime import date

from quaoar.checks.litigation import LitigationFindings, Matter, undisclosed_before
from quaoar.domain.findings import Signal, Status


def litigation_signals(f: LitigationFindings, cutoff: date | None) -> list[Signal]:
    extra = undisclosed_before(f, cutoff)
    subjects = len(f.subjects)
    if extra:
        # promoters are never named on the card: matching people by name alone is unreliable
        who = "the issuer" if any(m.about_issuer for m in extra) else "the issuer and a promoter"
        text = (
            f"{len(extra)} court or SEBI matter(s) naming {who} turned up in search that the "
            f"prospectus's litigation section ({f.disclosed_count} disclosed) doesn't list: worth a closer look."
        )
        return [lt(f, Status.INCONSISTENT, text, extra, cutoff)]
    where = f" before {cutoff:%b %Y}" if cutoff else ""
    text = (
        f"No court or SEBI matter naming the issuer or {subjects - 1} promoters turned up in search{where} "
        f"beyond the {f.disclosed_count} the prospectus discloses."
    )
    return [lt(f, Status.CONSISTENT, text, [], cutoff)]


def lt(
    f: LitigationFindings, status: Status, text: str, extra: list[Matter], cutoff: date | None
) -> Signal:
    return Signal(
        check="litigation", rule="LT-03", subject=f.issuer, status=status, text=text,
        observed=f"{len(extra)} undisclosed of {len(f.matters)} found", page=f.page,
        evidence=tuple(m.evidence for m in extra[:3]), pit_ok=cutoff is not None,
    )  # fmt: skip
