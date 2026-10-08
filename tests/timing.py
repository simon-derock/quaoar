# timing budgets scale with QUAOAR_PERF_SCALE so slower CI runners do not flake
import os

SCALE = float(os.environ.get("QUAOAR_PERF_SCALE", "1"))


def budget_seconds(seconds: float) -> float:
    return seconds * SCALE
