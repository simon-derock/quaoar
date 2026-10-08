# spec: SPEC-PRF-01
import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from quaoar.domain.money import parse_inr
from tests.perf.conftest import median_seconds
from tests.timing import budget_seconds


@pytest.mark.perf
def test_parse_inr_median_under_20_microseconds(benchmark: BenchmarkFixture) -> None:
    benchmark(parse_inr, "Rs. 17.70 crore")
    assert median_seconds(benchmark) < budget_seconds(20e-6)
