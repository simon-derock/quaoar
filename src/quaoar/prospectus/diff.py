# what changed between two versions of the same prospectus (draft, red herring, final)
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from quaoar.domain.claims import (
    DisclosedCaseClaim,
    Grounded,
    GroupCompanyClaim,
    LeadManagerClaim,
    PastIssueClaim,
    PlaceClaim,
    PromoterClaim,
    QuoteClaim,
)
from quaoar.domain.money import MoneyParseError, format_inr, parse_inr
from quaoar.domain.names import normalize_company

NOISE = re.compile(r"[^a-z0-9]+")
LABELS = {
    "quotes": "vendor quotation",
    "cases": "disclosed matter",
    "lead_managers": "lead manager",
    "promoters": "promoter",
    "group_companies": "group company",
    "places": "place of business",
    "past_issues": "past issue of the lead manager",
}


@dataclass(frozen=True, slots=True)
class Change:
    kind: str
    group: str
    text: str
    page_old: int | None
    page_new: int | None


def diff_claims(
    old: Mapping[str, Sequence[Grounded]], new: Mapping[str, Sequence[Grounded]]
) -> list[Change]:
    changes: list[Change] = []
    for group in LABELS:
        before = {key_of(c): c for c in old.get(group, [])}
        after = {key_of(c): c for c in new.get(group, [])}
        changes.extend(
            Change(
                "removed",
                group,
                f"{LABELS[group]} in the earlier version only: {describe(before[k])}",
                before[k].page,
                None,
            )
            for k in sorted(before.keys() - after.keys())
        )
        changes.extend(
            Change(
                "added",
                group,
                f"{LABELS[group]} in the later version only: {describe(after[k])}",
                None,
                after[k].page,
            )
            for k in sorted(after.keys() - before.keys())
        )
        for key in sorted(before.keys() & after.keys()):
            changed = changed_text(before[key], after[key])
            if changed:
                changes.append(Change("changed", group, changed, before[key].page, after[key].page))
    return changes


def key_of(claim: Grounded) -> str:
    if isinstance(claim, QuoteClaim):
        return normalize_company(claim.vendor)
    if isinstance(claim, DisclosedCaseClaim):
        return (
            NOISE.sub("", claim.case_ref.lower())
            or normalize_company(claim.party) + "|" + claim.forum.lower()
        )
    if isinstance(claim, PlaceClaim):
        return f"{claim.role}|{claim.city.lower()}|{claim.locality.lower()}"
    if isinstance(claim, PastIssueClaim):
        return normalize_company(claim.issuer)
    if isinstance(claim, LeadManagerClaim | PromoterClaim | GroupCompanyClaim):
        return normalize_company(claim.name)
    return claim.span


def describe(claim: Grounded) -> str:
    if isinstance(claim, QuoteClaim):
        return f"{claim.vendor} ({money(claim)})"
    if isinstance(claim, DisclosedCaseClaim):
        return f"{claim.forum} {claim.case_ref}".strip() or claim.party
    if isinstance(claim, PlaceClaim):
        return f"{claim.role.replace('_', ' ')}, {claim.locality}, {claim.city}"
    if isinstance(claim, PastIssueClaim):
        return claim.issuer
    return str(getattr(claim, "name", claim.span))


def changed_text(before: Grounded, after: Grounded) -> str | None:
    if isinstance(before, QuoteClaim) and isinstance(after, QuoteClaim):
        a, b = amount(before), amount(after)
        if a is not None and b is not None and a != b:
            return f"vendor quotation from {after.vendor} changed: {format_inr(a, 'short')} earlier, {format_inr(b, 'short')} later"
        if a is None and b is None and before.amount_text != after.amount_text:
            return f"vendor quotation from {after.vendor} changed: {before.amount_text} earlier, {after.amount_text} later"
    return None


def amount(claim: QuoteClaim) -> int | None:
    try:
        return parse_inr(claim.amount_text, unit=claim.unit_text or None)
    except MoneyParseError:
        return None


def money(claim: QuoteClaim) -> str:
    paise = amount(claim)
    return format_inr(paise, "short") if paise is not None else claim.amount_text
