"""Export the governed OpenAPI contract to docs/openapi.json (repo root).

Run: python -m scripts.export_openapi
Keeps a static, reviewable copy of the API contract in version control (§8).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

OUT = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def export() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"OpenAPI written to {OUT}")


if __name__ == "__main__":
    export()
