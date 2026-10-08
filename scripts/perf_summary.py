# turns pytest-benchmark json into a markdown table for the CI job summary
import json
import sys
from pathlib import Path


def main(path: str) -> None:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = ["| benchmark | median | min | max |", "|---|---:|---:|---:|"]
    for bench in data["benchmarks"]:
        stats = bench["stats"]
        cells = [human(stats[key]) for key in ("median", "min", "max")]
        rows.append(f"| {bench['name']} | " + " | ".join(cells) + " |")
    sys.stdout.write("\n".join(rows) + "\n")


def human(seconds: float) -> str:
    # ns under a microsecond, µs under a millisecond, ms above
    if seconds < 1e-6:
        return f"{seconds * 1e9:.0f} ns"
    if seconds < 1e-3:
        return f"{seconds * 1e6:.2f} µs"
    return f"{seconds * 1e3:.2f} ms"


if __name__ == "__main__":
    main(sys.argv[1])
