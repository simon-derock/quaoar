# site-visit rules: a listing must exist, be open, and not be a home or a shared desk for a factory
from quaoar.checks.site import SiteFindings
from quaoar.domain.findings import Signal, Status

RESIDENTIAL_TYPES = ("apartment", "housing", "residential", "co-working", "coworking", "villa")
WORKPLACES = frozenset({"factory", "warehouse"})


def site_signals(f: SiteFindings) -> list[Signal]:
    where = f"{f.locality}, {f.city}".strip(", ")
    label = f.role.replace("_", " ")
    if not f.maps.found:
        text = f"Couldn't find the {label} ({where}) on Google Maps."
        return [site(f, "SV-02", Status.UNVERIFIED, text)]
    if "permanently closed" in f.maps.open_state.lower():
        text = f"The Google Maps listing for the {label} ({where}) is marked permanently closed."
        return [site(f, "SV-02", Status.INCONSISTENT, text)]

    kind = f" (listed as {f.place_type.lower()})" if f.place_type else ""
    signals = [
        site(
            f, "SV-02", Status.CONSISTENT, f"The {label} ({where}) has a Google Maps listing{kind}."
        )
    ]
    if f.role in WORKPLACES and any(t in f.place_type.lower() for t in RESIDENTIAL_TYPES):
        text = f"The prospectus describes a {label} at {where}, but Google Maps lists the place as {f.place_type.lower()}: worth a closer look."
        signals.append(site(f, "SV-04", Status.INCONSISTENT, text))
    return signals


def site(f: SiteFindings, rule: str, status: Status, text: str) -> Signal:
    return Signal(
        check="site", rule=rule, subject=f.issuer, status=status, text=text, page=f.page,
        evidence=tuple(f.evidence if status is not Status.UNVERIFIED else ()),
    )  # fmt: skip
