# footprint rules: adverse dated coverage before the cutoff is a mismatch; promotion volume is context only
from datetime import date

from quaoar.checks.footprint import FootprintFindings
from quaoar.domain.findings import Signal, Status


def footprint_signals(f: FootprintFindings, cutoff: date | None) -> list[Signal]:
    adverse = [
        a
        for a in f.articles
        if a.adverse and (cutoff is None or (a.when is not None and a.when <= cutoff))
    ]
    when = f" before {cutoff:%b %Y}" if cutoff else ""
    if adverse:
        text = f"{len(adverse)} news article(s) about {f.issuer} mentioning SEBI action, a complaint or a halt turned up{when}: worth a closer look."
        news = Signal(
            check="footprint", rule="NW-01", subject=f.issuer, status=Status.INCONSISTENT, text=text,
            observed=f"{len(adverse)} of {len(f.articles)} articles", evidence=tuple(a.evidence for a in adverse[:3]),
            pit_ok=cutoff is not None,
        )  # fmt: skip
    else:
        text = f"No news about {f.issuer} mentioning SEBI action, a complaint or a halt turned up{when}."
        news = Signal(
            check="footprint", rule="NW-01", subject=f.issuer, status=Status.CONSISTENT, text=text,
            observed=f"{len(f.articles)} articles read", pit_ok=cutoff is not None,
        )  # fmt: skip

    context = (
        f"Context, not a verdict: {f.videos} YouTube video(s) ({f.promo_videos} about price, applying or listing) "
        f"and {len(f.articles)} news article(s) name this IPO."
    )
    volume = Signal(
        check="footprint",
        rule="HY-01",
        subject=f.issuer,
        status=Status.NOT_APPLICABLE,
        text=context,
    )
    return [news, volume]
