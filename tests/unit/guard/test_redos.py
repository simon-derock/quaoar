# spec: SPEC-GRD-08
# every guard and parser must stay linear: 8x the input may cost about 8x the time,
# quadratic code would cost about 64x and catastrophic backtracking far more
import time
from collections.abc import Callable

import pytest

from quaoar.domain.dates import parse_date
from quaoar.domain.money import MoneyParseError, parse_inr
from quaoar.domain.names import normalize_company
from quaoar.guard.advice import advice_request
from quaoar.guard.injection import scan_injection
from quaoar.guard.pii import mask_pii
from quaoar.guard.secrets import SecretRedactor
from quaoar.guard.text import clean_text
from quaoar.guard.wording import banned_terms
from tests.timing import budget_seconds

SMALL, LARGE = 25_000, 200_000
MAX_GROWTH = 20
SEEDS = {
    "spaces": " ",
    "letters": "a",
    "digits": "1",
    "commas": "1,",
    "escape": "\x1b]x",
    "keywords": "flat ignore Rs. mark all ",
}


def money_or_none(text: str) -> int | None:
    try:
        return parse_inr(text)
    except MoneyParseError:
        return None


GUARDS: dict[str, Callable[[str], object]] = {
    "clean_text": clean_text,
    "scan_injection": scan_injection,
    "mask_pii": mask_pii,
    "redact": SecretRedactor(["s" * 40]).redact,
    "banned_terms": banned_terms,
    "advice_request": advice_request,
    "parse_inr": money_or_none,
    "parse_date": parse_date,
    "normalize_company": normalize_company,
}


@pytest.mark.parametrize("guard", sorted(GUARDS))
@pytest.mark.parametrize("seed", sorted(SEEDS))
def test_runs_in_linear_time_on_adversarial_input(guard: str, seed: str) -> None:
    run = GUARDS[guard]
    small = best_of_three(run, grow(SEEDS[seed], SMALL))
    large = best_of_three(run, grow(SEEDS[seed], LARGE))
    assert large < budget_seconds(0.1)

    # sub-millisecond timings are mostly noise, so the base gets a floor
    assert large < MAX_GROWTH * max(small, 1e-3)


def grow(seed: str, size: int) -> str:
    return (seed * (size // len(seed) + 1))[:size]


def best_of_three(run: Callable[[str], object], text: str) -> float:
    times = []
    for _ in range(3):
        start = time.perf_counter_ns()
        run(text)
        times.append((time.perf_counter_ns() - start) / 1e9)
    return min(times)
