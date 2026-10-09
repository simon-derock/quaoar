# deterministic rules: findings in, signals out; frozen before any labelled backtest run
from datetime import date

from quaoar.checks.vendor import VendorFindings
from quaoar.domain.findings import Evidence, Signal, Status
from quaoar.domain.money import format_inr

RULESET_VERSION = "1"
CAPITAL_RATIO_LIMIT = 100
PAID = "paid_up_paise"
STALE_MONTHS = 18
STRUCK_OFF = frozenset(
    {"strike off", "struck off", "under process of striking off", "dormant", "dissolved",
     "liquidated", "under liquidation", "amalgamated"}
)  # fmt: skip


def vendor_signals(f: VendorFindings, cutoff: date | None) -> list[Signal]:
    return [
        registry_signal(f),
        capital_signal(f),
        status_signal(f, cutoff),
        presence_signal(f),
        legal_signal(f, cutoff),
    ]


def registry_signal(f: VendorFindings) -> Signal:
    if not f.registry.matched_urls:
        return vx(
            f, "VX-02", Status.UNVERIFIED, f"Couldn't find {f.vendor} on company-registry pages."
        )
    details = ", ".join(
        part
        for part in (
            f"CIN {f.registry.cin}" if f.registry.cin else "",
            f"incorporated {f.registry.incorporated:%d %b %Y}" if f.registry.incorporated else "",
        )
        if part
    )
    text = f"{f.vendor} is on public company-registry pages" + (
        f" ({details})." if details else "."
    )
    return vx(f, "VX-02", Status.CONSISTENT, text, registry=True, fact="cin")


def capital_signal(f: VendorFindings) -> Signal:
    paid, quote = f.registry.paid_up_paise, f.quote_paise
    if not paid or not quote:
        return vx(f, "VX-03", Status.UNVERIFIED, f"Couldn't read {f.vendor}'s paid-up capital.")

    ratio = quote / paid
    observed = (
        f"quote {format_inr(quote, 'short')} vs paid-up {format_inr(paid, 'short')} ({ratio:,.0f}x)"
    )
    if ratio >= CAPITAL_RATIO_LIMIT:
        text = (
            f"{f.vendor} quoted {format_inr(quote, 'short')}, but its paid-up capital on registry "
            f"pages is {format_inr(paid, 'short')}: the quote is {ratio:,.0f} times its capital."
        )
        return vx(
            f, "VX-03", Status.INCONSISTENT, text, observed=observed, registry=True, fact=PAID
        )
    text = (
        f"{f.vendor}'s paid-up capital ({format_inr(paid, 'short')}) is in proportion to its quote."
    )
    return vx(f, "VX-03", Status.CONSISTENT, text, observed=observed, registry=True, fact=PAID)


def status_signal(f: VendorFindings, cutoff: date | None) -> Signal:
    status, sheet = f.registry.status, f.registry.last_balance_sheet
    if status in STRUCK_OFF:
        return vx(
            f,
            "VX-04",
            Status.INCONSISTENT,
            f"Registry pages list {f.vendor} as '{status}'.",
            registry=True,
            fact="status",
        )
    if sheet and cutoff and months_between(sheet, cutoff) > STALE_MONTHS:
        text = f"{f.vendor}'s last balance sheet on record is dated {sheet:%d %b %Y}, over {STALE_MONTHS} months before the prospectus."
        return vx(f, "VX-04", Status.INCONSISTENT, text, registry=True, fact="last_balance_sheet")
    if status == "active":
        return vx(
            f,
            "VX-04",
            Status.CONSISTENT,
            f"Registry pages list {f.vendor} as active.",
            registry=True,
            fact="status",
        )
    return vx(f, "VX-04", Status.UNVERIFIED, f"Couldn't read {f.vendor}'s registry status.")


def presence_signal(f: VendorFindings) -> Signal:
    if not f.maps.found:
        return vx(f, "VX-05", Status.UNVERIFIED, f"Couldn't find {f.vendor} on Google Maps.")
    if "permanently closed" in f.maps.open_state.lower():
        text = f"{f.vendor}'s Google Maps listing is marked permanently closed."
        return vx(f, "VX-05", Status.INCONSISTENT, text)
    where = f" ({f.maps.city_area})" if f.maps.city_area else ""
    return vx(f, "VX-05", Status.CONSISTENT, f"{f.vendor} has a Google Maps listing{where}.")


def legal_signal(f: VendorFindings, cutoff: date | None) -> Signal:
    # a matter counts when it is dated on or before the cutoff; with no cutoff every dated or undated one counts
    hits = [m for m in f.legal if cutoff is None or (m.when is not None and m.when <= cutoff)]
    if hits:
        text = (
            f"{len(hits)} court or SEBI page(s) naming {f.vendor} turned up in search"
            f"{'' if cutoff is None else f' before {cutoff:%b %Y}'}: worth a closer look."
        )
        return Signal(
            check="vendor", rule="VX-06", subject=f.vendor, status=Status.INCONSISTENT, text=text,
            observed=f"{len(hits)} matter(s)", page=f.page,
            evidence=tuple(m.evidence for m in hits[:3]), pit_ok=cutoff is not None,
        )  # fmt: skip
    text = f"No court or SEBI page naming {f.vendor} turned up in search."
    return Signal(
        check="vendor", rule="VX-06", subject=f.vendor, status=Status.CONSISTENT, text=text,
        page=f.page, pit_ok=cutoff is not None,
    )  # fmt: skip


def vx(
    f: VendorFindings,
    rule: str,
    status: Status,
    text: str,
    *,
    observed: str = "",
    registry: bool = False,
    fact: str | None = None,
) -> Signal:
    evidence = proof(f, fact) if registry else f.maps_evidence
    threshold = f"{CAPITAL_RATIO_LIMIT}x" if rule == "VX-03" else ""
    return Signal(
        check="vendor",
        rule=rule,
        subject=f.vendor,
        status=status,
        text=text,
        observed=observed,
        threshold=threshold,
        page=f.page,
        evidence=tuple(evidence if status is not Status.UNVERIFIED else ()),
        pit_ok=False,
    )


def proof(f: VendorFindings, fact: str | None) -> list[Evidence]:
    # show the page that stated this fact; fall back to the first registry page
    source = f.registry.sources.get(fact) if fact else None
    stated = [e for e in f.registry_evidence if e.url == source]
    return stated or f.registry_evidence[:1]


def months_between(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + later.month - earlier.month
