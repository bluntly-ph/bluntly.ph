"""`cd backend && python -m sim` — regenerate every figure, CSV, and summary table.

Idempotent: the scenarios are seeded, so re-running overwrites with identical
output. Writes PNGs to docs/assets/ranking/ and CSVs to docs/assets/ranking/data/.
"""

from __future__ import annotations

import csv
from pathlib import Path

from sim import scenarios as S
from sim.charts import OUT_DIR, render_all

DATA_DIR = OUT_DIR / "data"


def write_csvs() -> list[Path]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for name, rows in S.summary_rows().items():
        path = DATA_DIR / f"{name}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        written.append(path)
    return written


def print_facts() -> None:
    facts = S.headline_facts()
    width = max(len(k) for k in facts)
    print("\nHeadline facts (these are what the document quotes)\n" + "-" * 62)
    for key, value in facts.items():
        if isinstance(value, float):
            value = f"{value:.4f}"
        print(f"  {key:<{width}}  {value}")


def main() -> None:
    figures = render_all()
    csvs = write_csvs()
    print(f"Figures written to {OUT_DIR}")
    for path in figures:
        print(f"  {path.name}")
    print(f"\nData written to {DATA_DIR}")
    for path in csvs:
        print(f"  {path.name}")
    print_facts()


if __name__ == "__main__":
    main()
