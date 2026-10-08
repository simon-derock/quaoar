# banker rules: any SEBI order naming the banker or a past issuer, dated before the cutoff, is a mismatch
from datetime import date

from quaoar.checks.banker import BankerFindings, before
from quaoar.domain.findings import Evidence, Signal, Status


def banker_signals(f: BankerFindings, cutoff: date | None) -> list[Signal]:
    return [own_orders_signal(f, cutoff), past_issues_signal(f, cutoff)]


def own_orders_signal(f: BankerFindings, cutoff: date | None) -> Signal:
    hits = before(f.banker_orders, cutoff)
    if hits:
        first = min(hits, key=lambda h: h.month or date.max)
        when = f"{first.month:%b %Y}" if first.month else "an earlier date"
        text = f"A SEBI order naming {f.banker} turned up in search, dated {when}."
        return bk(f, "BK-04", Status.INCONSISTENT, text, [h.evidence for h in hits[:2]], pit=cutoff)
    text = f"No SEBI order naming {f.banker} turned up in search" + (
        f" before {cutoff:%b %Y}." if cutoff else "."
    )
    return bk(f, "BK-04", Status.CONSISTENT, text, [], pit=cutoff)


def past_issues_signal(f: BankerFindings, cutoff: date | None) -> Signal:
    if not f.past_issuers:
        return bk(
            f,
            "BK-05",
            Status.UNVERIFIED,
            f"Couldn't read {f.banker}'s past-issues table.",
            [],
            pit=cutoff,
        )

    flagged = {name: before(hits, cutoff) for name, hits in f.issuer_orders.items()}
    flagged = {name: hits for name, hits in flagged.items() if hits}
    observed = f"{len(flagged)} of {len(f.past_issuers)} past issues"
    if flagged:
        names = ", ".join(sorted(flagged))
        text = f"SEBI orders naming past issuers of {f.banker} turned up in search: {names} ({observed})."
        proof = [h.evidence for hits in flagged.values() for h in hits[:1]][:3]
        return bk(f, "BK-05", Status.INCONSISTENT, text, proof, pit=cutoff, observed=observed)
    count = len(f.past_issuers)
    noun = "past issuer" if count == 1 else f"{count} past issuers"
    text = f"No SEBI order naming {noun} of {f.banker} turned up in search."
    return bk(f, "BK-05", Status.CONSISTENT, text, [], pit=cutoff, observed=observed)


def bk(
    f: BankerFindings,
    rule: str,
    status: Status,
    text: str,
    proof: list[Evidence],
    *,
    pit: date | None,
    observed: str = "",
) -> Signal:
    return Signal(
        check="banker", rule=rule, subject=f.banker, status=status, text=text,
        observed=observed, page=f.page, evidence=tuple(proof), pit_ok=pit is not None,
    )  # fmt: skip
