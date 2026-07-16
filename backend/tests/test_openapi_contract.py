"""OpenAPI contract health (M3 slice 13).

The frontend builds against docs/openapi.json and lib/api-types.d.ts. These
checks stop the spec silently rotting: an untagged route or a missing problem
schema turns into a bad generated client.
"""

from __future__ import annotations

import json
import pathlib

from app.main import app

SPEC = pathlib.Path(__file__).resolve().parents[2] / "docs" / "openapi.json"
TYPES = pathlib.Path(__file__).resolve().parents[2] / "lib" / "api-types.d.ts"


def _live_spec() -> dict:
    return app.openapi()


def test_every_operation_is_tagged():
    """An untagged route lands in a junk 'default' group in the generated client."""
    untagged = [f"{m.upper()} {p}" for p, item in _live_spec()["paths"].items()
                for m, op in item.items() if not op.get("tags")]
    assert untagged == [], f"untagged operations: {untagged}"


def test_every_operation_has_a_summary():
    missing = [f"{m.upper()} {p}" for p, item in _live_spec()["paths"].items()
               for m, op in item.items() if not op.get("summary")]
    assert missing == [], f"operations without a summary: {missing}"


def test_exported_spec_is_in_sync_with_the_app():
    """docs/openapi.json is committed and consumed by `npm run gen:api`; a stale
    file silently ships wrong types."""
    assert SPEC.exists(), "docs/openapi.json missing — run scripts.export_openapi"
    exported = json.loads(SPEC.read_text(encoding="utf-8"))
    live = _live_spec()
    assert set(exported["paths"]) == set(live["paths"]), (
        "docs/openapi.json is stale — re-run `python -m scripts.export_openapi`")


def test_generated_types_exist_and_cover_m3():
    assert TYPES.exists(), "lib/api-types.d.ts missing — run `npm run gen:api`"
    text = TYPES.read_text(encoding="utf-8", errors="replace")
    for path in ("/api/v1/requests", "/api/v1/contracts", "/api/v1/payouts",
                 "/api/v1/tokens/balance"):
        assert path in text, f"{path} missing from generated types — re-run gen:api"


def test_m3_surfaces_are_present():
    paths = set(_live_spec()["paths"])
    for p in ("/api/v1/requests", "/api/v1/requests/{request_id}/fulfill",
              "/api/v1/contracts", "/api/v1/contracts/{contract_id}/buyout/accept",
              "/api/v1/payouts", "/api/v1/admin/payouts/run",
              "/api/v1/auth/me/payout-account", "/api/v1/admin/commissions/import"):
        assert p in paths, f"missing endpoint: {p}"
