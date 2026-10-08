# timing budgets scale with QUAOAR_PERF_SCALE so slower CI runners do not flake
import os

from pytest_benchmark.fixture import BenchmarkFixture

SCALE = float(os.environ.get("QUAOAR_PERF_SCALE", "1"))


def budget_seconds(seconds: float) -> float:
    return seconds * SCALE


def median_seconds(benchmark: BenchmarkFixture) -> float:
    # stats stay empty when benchmarks are disabled, which would hide a broken budget
    assert benchmark.stats is not None, "run perf tests with benchmarks enabled"
    return float(benchmark.stats.stats.median)
