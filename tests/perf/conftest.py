# shared perf helpers; budgets come from tests.timing
from pytest_benchmark.fixture import BenchmarkFixture


def median_seconds(benchmark: BenchmarkFixture) -> float:
    # stats stay empty when benchmarks are disabled, which would hide a broken budget
    assert benchmark.stats is not None, "run perf tests with benchmarks enabled"
    return float(benchmark.stats.stats.median)
