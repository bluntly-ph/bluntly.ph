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


# --------------------------------------------------------------------------- #
# Reading telemetry is never exposed over the API (spec §8, §15)
# --------------------------------------------------------------------------- #

_METHODS = {"get", "post", "put", "patch", "delete"}

# The brief's literal list. `staff_ref` / `is_super_admin` legitimately appear in
# the authorised staff User Management schemas under `/api/v1/admin/...`; the
# public checks below exclude that prefix, so those two are asserted absent from
# every *public* response, and the six telemetry names are asserted absent from
# every response anywhere.
FORBIDDEN = {
    "anon_ref", "reader_ref", "impression_id", "reader_kind",
    "active_ms", "body_active_ms", "staff_ref", "is_super_admin",
}
TELEMETRY_ONLY = {
    "anon_ref", "reader_ref", "impression_id", "reader_kind",
    "active_ms", "body_active_ms",
}
_STAFF_EXEMPT_PREFIX = "/api/v1/admin"


def _resolve_ref(spec: dict, ref: str) -> dict:
    node: dict = spec
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def _property_names(spec: dict, schema: dict | None, seen: set[str]) -> set[str]:
    """Every property name reachable from a schema node, resolving `$ref`."""
    if not isinstance(schema, dict):
        return set()
    ref = schema.get("$ref")
    if ref:
        if ref in seen:
            return set()
        seen.add(ref)
        return _property_names(spec, _resolve_ref(spec, ref), seen)
    names: set[str] = set()
    for combinator in ("allOf", "anyOf", "oneOf"):
        for sub in schema.get(combinator, []):
            names |= _property_names(spec, sub, seen)
    props = schema.get("properties")
    if isinstance(props, dict):
        for prop_name, prop_schema in props.items():
            names.add(prop_name)
            names |= _property_names(spec, prop_schema, seen)
    for nested_key in ("items", "additionalProperties"):
        nested = schema.get(nested_key)
        if isinstance(nested, dict):
            names |= _property_names(spec, nested, seen)
    return names


def _response_field_names(spec: dict, operation: dict) -> set[str]:
    names: set[str] = set()
    for response in operation.get("responses", {}).values():
        for media in response.get("content", {}).values():
            names |= _property_names(spec, media.get("schema"), set())
    return names


def _operations(spec: dict):
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method in _METHODS:
                yield path, method, operation


def test_no_response_schema_anywhere_returns_reading_telemetry():
    """Nothing reads this data back over HTTP in Phase 1 — not even for staff."""
    spec = _live_spec()
    offenders = {
        f"{method.upper()} {path}": leaked
        for path, method, operation in _operations(spec)
        if (leaked := _response_field_names(spec, operation) & TELEMETRY_ONLY)
    }
    assert not offenders, f"reading telemetry reachable via a response: {offenders}"


def test_no_public_response_or_get_operation_exposes_a_forbidden_field():
    spec = _live_spec()
    offenders: dict[str, set[str]] = {}
    for path, method, operation in _operations(spec):
        if path.startswith(_STAFF_EXEMPT_PREFIX):
            continue
        names = _response_field_names(spec, operation)
        if method == "get":
            names |= {p.get("name") for p in operation.get("parameters", [])}
        if leaked := names & FORBIDDEN:
            offenders[f"{method.upper()} {path}"] = leaked
    assert not offenders, f"forbidden fields on a public surface: {offenders}"


def test_the_ingest_request_schema_is_write_only():
    """`ReadingCheckpointIn` is a request body on exactly the private ingest
    POST, and appears in no response schema and no public review/feed/profile
    model."""
    spec = _live_spec()
    ingest = spec["paths"]["/api/v1/internal/reading-telemetry"]["post"]
    body_ref = ingest["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert body_ref.endswith("/ReadingCheckpointIn")

    for path, method, operation in _operations(spec):
        for response in operation.get("responses", {}).values():
            for media in response.get("content", {}).values():
                blob = json.dumps(media.get("schema", {}))
                assert "ReadingCheckpointIn" not in blob, (
                    f"the ingest request schema leaked into {method.upper()} {path}")

    from app.schemas.auth import UserOut
    from app.schemas.review import FeedItemOut, ReviewOut

    for schema in (ReviewOut, FeedItemOut, UserOut):
        for field in ("impression_id", "active_ms", "reader_kind", "anon_ref"):
            assert field not in schema.model_fields, f"{schema.__name__}.{field}"
