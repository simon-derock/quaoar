# spec: SPEC-PRF-05
import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from quaoar.prospectus.pdf import Page
from quaoar.prospectus.sections import locate_sections
from tests.perf.conftest import median_seconds
from tests.timing import budget_seconds

TITLES = [f"CHAPTER {i} TITLE" for i in range(40)]


def document(pages: int = 300) -> list[Page]:
    toc = "\n".join(["TABLE OF CONTENTS", *(f"{t} ........ {i}" for i, t in enumerate(TITLES))])
    out = [Page(1, toc, needs_ocr=False)]
    for number in range(2, pages + 1):
        heading = TITLES[number // 8] if number % 8 == 0 and number // 8 < len(TITLES) else "BODY"
        text = "\n".join(
            [
                f"{number} | P a g e",
                heading,
                *("lorem ipsum dolor sit amet " * 6 for _ in range(40)),
            ]
        )
        out.append(Page(number, text, needs_ocr=False))
    return out


@pytest.mark.perf
def test_section_locator_on_300_pages_under_50_ms(benchmark: BenchmarkFixture) -> None:
    pages = document()
    benchmark(locate_sections, pages)
    assert median_seconds(benchmark) < budget_seconds(50e-3)
