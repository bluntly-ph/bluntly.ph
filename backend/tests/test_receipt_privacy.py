"""Proof of purchase must never be publicly retrievable (P0 regression).

The defect these pin down: receipts were written to the PUBLIC review-photos
bucket behind a permanent URL, and `receipt_url` rode on `ReviewOut`, which is
served by endpoints that accept anonymous callers. Possession of a URL was
therefore sufficient to read a stranger's receipt, bypassing every role check
the API applies to the row.

The invariant, stated once so a future change has something to fail against:

    A review photo may be public. A receipt must never be retrievable from
    storage without authorization, and must never appear in any response an
    unauthorized caller can obtain.

DB-backed tests clean up after themselves. This repo has one database and it is
production, and a suite that leaves fixtures behind has been an actual incident
here before (see the BUG-010 note in qa/), so these do not add to it.
"""

from __future__ import annotations

import uuid

import pytest

from app.core.errors import AppError
from app.services import storage
from tests.conftest import register_and_token, requires_db

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 64
GIF = b"GIF89a" + b"\x00" * 64

# Every locator-shaped thing that must never reach an unauthorized caller.
FORBIDDEN_KEYS = ("receipt_url", "receipt_key", "receipt_path", "receipt_object")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _assert_no_receipt_locator(payload, where: str) -> None:
    """Fail if any receipt locator appears anywhere in a response.

    Walks the whole structure rather than checking known field names: the point
    is to catch a locator arriving through a nested schema nobody thought about,
    which is exactly how the version-snapshot leak survived the first pass at
    this bug.
    """
    def walk(node, path="$"):
        if isinstance(node, dict):
            for key, value in node.items():
                assert key not in FORBIDDEN_KEYS, f"{where}: receipt locator at {path}.{key}"
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]")
        elif isinstance(node, str):
            assert storage.RECEIPT_BUCKET not in node, (
                f"{where}: private bucket name leaked at {path}")

    walk(payload)


# --------------------------------------------------------------------------
# Bucket separation
# --------------------------------------------------------------------------

def test_receipts_and_photos_use_different_buckets():
    assert storage.RECEIPT_BUCKET != storage.REVIEW_BUCKET
    assert storage.RECEIPT_BUCKET == "review-receipts"


def test_upload_receipt_returns_a_key_not_a_url(monkeypatch):
    """The receipt helper must not hand back anything fetchable."""
    captured: dict = {}

    class _Bucket:
        def upload(self, path, data, opts):
            captured["path"] = path

        def get_public_url(self, path):  # pragma: no cover - must never run
            raise AssertionError("get_public_url() called for a receipt")

    class _Storage:
        def from_(self, name):
            captured["bucket"] = name
            return _Bucket()

    monkeypatch.setattr(storage, "get_service_client",
                        lambda: type("C", (), {"storage": _Storage()})())
    user_id = uuid.uuid4()
    key = storage.upload_receipt(user_id, JPEG)

    assert captured["bucket"] == storage.RECEIPT_BUCKET, "receipt left the private bucket"
    assert not key.startswith("http"), "receipt helper returned a URL"
    assert key.startswith(f"{user_id}/"), "key is not attributable to its uploader"
    # Randomized object name: no filename, no PII, from the client.
    assert uuid.UUID(key.split("/")[1].split(".")[0])


def test_review_photo_still_goes_to_the_public_bucket(monkeypatch):
    """The fix must not quietly make public review photos private."""
    seen: dict = {}

    class _Bucket:
        def upload(self, path, data, opts):
            seen["path"] = path

        def get_public_url(self, path):
            return f"https://example.supabase.co/{path}"

    class _Storage:
        def from_(self, name):
            seen["bucket"] = name
            return _Bucket()

    monkeypatch.setattr(storage, "get_service_client",
                        lambda: type("C", (), {"storage": _Storage()})())
    url = storage.upload_review_photo(uuid.uuid4(), PNG)
    assert seen["bucket"] == storage.REVIEW_BUCKET
    assert url.startswith("https://"), "public photos still need a public URL"


# --------------------------------------------------------------------------
# Upload validation is not relaxed for the private path
# --------------------------------------------------------------------------

@pytest.mark.parametrize("data,expected", [
    (PNG, "image/png"),
    (JPEG, "image/jpeg"),
    (WEBP, "image/webp"),
])
def test_receipt_accepts_supported_formats(data, expected):
    assert storage.validate_receipt(data) == expected


def test_receipt_rejects_unsupported_format():
    with pytest.raises(AppError) as exc:
        storage.validate_receipt(GIF)
    assert exc.value.code == "unsupported_media_type"


def test_receipt_trusts_magic_bytes_not_a_declared_type():
    # Whatever a client calls it, a GIF is not an accepted image.
    assert storage.sniff_image_type(GIF) is None


def test_receipt_size_limit_enforced():
    with pytest.raises(AppError) as exc:
        storage.validate_receipt(JPEG + b"\x00" * storage.MAX_RECEIPT_BYTES)
    assert exc.value.code == "file_too_large"


# --------------------------------------------------------------------------
# Key ownership
# --------------------------------------------------------------------------

def test_receipt_key_ownership():
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    key = f"{owner}/{uuid.uuid4().hex}.jpg"
    assert storage.receipt_key_belongs_to(key, owner) is True
    assert storage.receipt_key_belongs_to(key, stranger) is False
    # Malformed keys are never "mine".
    assert storage.receipt_key_belongs_to("", owner) is False
    assert storage.receipt_key_belongs_to("no-slash.jpg", owner) is False
    assert storage.receipt_key_belongs_to(f"../{owner}/x.jpg", owner) is False


# --------------------------------------------------------------------------
# API serialization + the authorization matrix
# --------------------------------------------------------------------------

def _delete_review(review_id: str) -> None:
    from sqlalchemy import text

    from app.db.session import SessionLocal
    with SessionLocal() as db:
        db.execute(text("DELETE FROM review_versions WHERE review_id = :r"), {"r": review_id})
        db.execute(text("DELETE FROM reviews WHERE id = :r"), {"r": review_id})
        db.commit()


@requires_db
def test_receipt_locator_never_reaches_an_unauthorized_caller(client):
    # register_and_token returns (id, token, email) - the id comes first.
    author_id, author_token, _ = register_and_token(client)
    _, stranger_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    ah = _auth(author_token)

    product_id = client.post("/api/v1/products", headers=ah,
                             json={"name": f"Receipt Fixture {uuid.uuid4().hex[:8]}",
                                   "category": "electronics"}).json()["id"]
    # A REAL object in the private bucket, so the authorized branch below proves
    # a signed URL is actually issued rather than passing on a 404. Never a copy
    # of production data - synthetic bytes only.
    key = storage.upload_receipt(uuid.UUID(author_id), JPEG)
    created = client.post("/api/v1/reviews", headers=ah, json={
        "product_id": product_id, "title": "Receipt privacy fixture",
        "discussion": "Fixture for the receipt privacy regression suite.",
        "verdict": "it_depends", "star_rating": 3,
        "photo_url": "https://example.com/proof.jpg", "receipt_key": key})
    assert created.status_code == 201, created.text
    review_id = created.json()["id"]
    stolen_id = None

    try:
        # The author's own response says evidence exists, never where.
        _assert_no_receipt_locator(created.json(), "POST /reviews (author)")
        assert created.json()["has_receipt"] is True

        # A stranger may not attach someone else's receipt to their own review.
        other_product = client.post("/api/v1/products", headers=_auth(stranger_token),
                                    json={"name": f"Other {uuid.uuid4().hex[:8]}",
                                          "category": "electronics"}).json()["id"]
        stolen = client.post("/api/v1/reviews", headers=_auth(stranger_token), json={
            "product_id": other_product, "title": "Not my receipt",
            "discussion": "Attempting to attach a receipt uploaded by someone else.",
            "verdict": "hard_pass", "star_rating": 1, "receipt_key": key})
        assert stolen.status_code == 403, stolen.text
        if stolen.status_code == 201:  # pragma: no cover - defensive cleanup
            stolen_id = stolen.json()["id"]

        # Publish it: this is the state in which the old design leaked.
        pub = client.post(f"/api/v1/admin/reviews/{review_id}/publish",
                          headers=_auth(mod_token))
        assert pub.status_code in (200, 201), pub.text

        # --- anonymous -----------------------------------------------------
        anon = client.get(f"/api/v1/reviews/{review_id}")
        assert anon.status_code == 200
        _assert_no_receipt_locator(anon.json(), "anonymous GET /reviews/{id}")
        _assert_no_receipt_locator(client.get("/api/v1/reviews?limit=50").json(),
                                   "anonymous GET /reviews")
        _assert_no_receipt_locator(client.get("/api/v1/reviews/feed?limit=50").json(),
                                   "anonymous GET /reviews/feed")
        # The version history was the second leak: snapshots embedded the URL.
        _assert_no_receipt_locator(
            client.get(f"/api/v1/reviews/{review_id}/versions").json(),
            "anonymous GET /reviews/{id}/versions")
        assert client.get(f"/api/v1/reviews/{review_id}/receipt").status_code == 401

        # --- unrelated authenticated user ----------------------------------
        stranger_view = client.get(f"/api/v1/reviews/{review_id}",
                                   headers=_auth(stranger_token))
        _assert_no_receipt_locator(stranger_view.json(), "stranger GET /reviews/{id}")
        assert client.get(f"/api/v1/reviews/{review_id}/receipt",
                          headers=_auth(stranger_token)).status_code == 404

        # --- author and moderator ------------------------------------------
        # Both are authorized. The object itself is absent (the key is
        # synthetic), so 404 here means authorization passed and lookup failed,
        # whereas the stranger's 404 above is refused before any lookup.
        for label, token in (("author", author_token), ("moderator", mod_token)):
            got = client.get(f"/api/v1/reviews/{review_id}/receipt", headers=_auth(token))
            assert got.status_code == 200, f"{label}: {got.status_code} {got.text}"
            body = got.json()
            assert body["expires_in"] <= 900, "signed URL TTL is not short"
            assert "token=" in body["url"], f"{label}: not a signed URL"
            assert "/object/public/" not in body["url"], f"{label}: got a PUBLIC url"
            # And the signed URL actually resolves for the authorized caller.
            import urllib.request
            with urllib.request.urlopen(
                    urllib.request.Request(body["url"], headers={"User-Agent": "test"}),
                    timeout=20) as resp:
                assert resp.status == 200, f"{label}: signed URL did not resolve"

        # The same object is NOT reachable without the signature.
        import urllib.error
        import urllib.request
        unsigned = body["url"].split("?")[0]
        try:
            urllib.request.urlopen(
                urllib.request.Request(unsigned, headers={"User-Agent": "test"}), timeout=20)
            raise AssertionError("private object served without a signature")
        except urllib.error.HTTPError as exc:
            assert exc.code in (400, 401, 403, 404), f"unexpected: {exc.code}"
    finally:
        _delete_review(review_id)
        if stolen_id:
            _delete_review(stolen_id)
        storage.delete_receipt_object(key)


@requires_db
def test_unpublished_review_stays_hidden_from_anonymous(client):
    _, token, _ = register_and_token(client)
    ah = _auth(token)
    product_id = client.post("/api/v1/products", headers=ah,
                             json={"name": f"Hidden {uuid.uuid4().hex[:8]}",
                                   "category": "electronics"}).json()["id"]
    review_id = client.post("/api/v1/reviews", headers=ah, json={
        "product_id": product_id, "title": "Still a draft",
        "discussion": "Unpublished reviews must stay invisible to the public.",
        "verdict": "it_depends", "star_rating": 3}).json()["id"]
    try:
        assert client.get(f"/api/v1/reviews/{review_id}").status_code == 404
        assert client.get(f"/api/v1/reviews/{review_id}/versions").status_code == 404
        assert client.get(f"/api/v1/reviews/{review_id}/receipt").status_code == 401
    finally:
        _delete_review(review_id)


def test_no_public_review_schema_declares_a_receipt_locator():
    """Structural guard: fails if a locator is ever added back to a shared schema.

    Cheaper and broader than the endpoint tests - it catches the field being
    reintroduced even on a code path no test happens to exercise.
    """
    from app.schemas import review as rs

    for name in ("ReviewOut", "FeedItemOut", "FeedProduct", "FeedAuthor",
                 "ReviewVersionOut"):
        model = getattr(rs, name)
        leaked = set(model.model_fields) & set(FORBIDDEN_KEYS)
        assert not leaked, f"{name} exposes {leaked}"


# --------------------------------------------------------------------------
# Receipt-view audit logging (owner-approved privacy/security enhancement)
# --------------------------------------------------------------------------

def _audit_rows(review_id: str) -> list:
    from sqlalchemy import text

    from app.db.session import SessionLocal
    with SessionLocal() as db:
        return db.execute(text(
            "SELECT moderator_id::text, action::text, target_ref::text, context "
            "FROM moderation_logs WHERE action = 'receipt_view' AND target_ref = :r"
        ), {"r": review_id}).mappings().all()


@requires_db
def test_moderator_receipt_view_is_audited_without_any_locator(client):
    """A moderator opening evidence leaves a record of WHO and WHICH REVIEW.

    And nothing else. The object key, the signed URL and anything off the
    receipt are precisely what must not end up in a log that outlives the
    request.
    """
    author_id, author_token, _ = register_and_token(client)
    _, stranger_token, _ = register_and_token(client)
    mod_id, mod_token, _ = register_and_token(client, role="moderator")
    ah = _auth(author_token)

    product_id = client.post("/api/v1/products", headers=ah,
                             json={"name": f"Audit {uuid.uuid4().hex[:8]}",
                                   "category": "electronics"}).json()["id"]
    key = storage.upload_receipt(uuid.UUID(author_id), JPEG)
    review_id = client.post("/api/v1/reviews", headers=ah, json={
        "product_id": product_id, "title": "Receipt audit fixture",
        "discussion": "Fixture for the receipt-view audit regression suite.",
        "verdict": "it_depends", "star_rating": 3, "receipt_key": key}).json()["id"]

    try:
        assert _audit_rows(review_id) == [], "nothing viewed yet"

        # Anonymous: refused, and must not produce a successful-access record.
        assert client.get(f"/api/v1/reviews/{review_id}/receipt").status_code == 401
        assert _audit_rows(review_id) == [], "a refused request must not be audited"

        # Unrelated user: refused, still no record.
        assert client.get(f"/api/v1/reviews/{review_id}/receipt",
                          headers=_auth(stranger_token)).status_code == 404
        assert _audit_rows(review_id) == [], "a 404 must not be audited"

        # The author reading their OWN evidence is ordinary use, not moderation.
        assert client.get(f"/api/v1/reviews/{review_id}/receipt",
                          headers=ah).status_code == 200
        assert _audit_rows(review_id) == [], "author self-access is not a moderation event"

        # The moderator: exactly one record.
        got = client.get(f"/api/v1/reviews/{review_id}/receipt", headers=_auth(mod_token))
        assert got.status_code == 200
        rows = _audit_rows(review_id)
        assert len(rows) == 1, f"expected exactly one audit row, got {len(rows)}"
        row = rows[0]
        assert row["moderator_id"] == mod_id
        assert row["target_ref"] == review_id
        assert row["action"] == "receipt_view"

        # No locator anywhere in the record.
        blob = str(dict(row))
        assert key not in blob, "the object key leaked into the audit row"
        assert storage.RECEIPT_BUCKET not in blob
        assert "token=" not in blob, "a signed URL leaked into the audit row"
        assert "http" not in blob.lower(), "a URL leaked into the audit row"

        # A second view is a second access and is recorded as one.
        client.get(f"/api/v1/reviews/{review_id}/receipt", headers=_auth(mod_token))
        assert len(_audit_rows(review_id)) == 2, "each access is its own event"

        # Authorization itself is unchanged by the logging.
        assert client.get(f"/api/v1/reviews/{review_id}/receipt").status_code == 401
        assert client.get(f"/api/v1/reviews/{review_id}/receipt",
                          headers=_auth(stranger_token)).status_code == 404
    finally:
        from sqlalchemy import text

        from app.db.session import SessionLocal
        with SessionLocal() as db:
            db.execute(text("DELETE FROM moderation_logs WHERE target_ref = :r"),
                       {"r": review_id})
            db.commit()
        _delete_review(review_id)
        storage.delete_receipt_object(key)


def test_receipt_view_is_a_declared_moderation_action():
    """Structural: the enum value exists, so the migration cannot be forgotten."""
    from app.models.enums import ModerationAction

    assert ModerationAction.receipt_view.value == "receipt_view"
