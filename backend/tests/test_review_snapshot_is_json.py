"""A review version snapshot has to be something `json.dumps` can write.

`review_versions.snapshot` is a JSONB column, and psycopg serialises it with the
standard library encoder — which raises on `Decimal`, `datetime`, `UUID` and
every enum. Nothing in the type system says so: the column is `dict`, and a
`dict` containing a `Decimal` is a perfectly good `dict` right up to the moment
a review is submitted.

That is not hypothetical. Migration 0048 turned `star_rating` into
`numeric(2,1)` so ratings could carry half steps, SQLAlchemy started returning
`Decimal`, and the next submission raised

    TypeError: Object of type Decimal is not JSON serializable

on the composer's last step. Twenty database-backed tests caught it, two hours
into CI, after the whole unit suite had passed.

This needs no database. It builds a review with every versioned field populated
the way the columns actually type them, and serialises the snapshot.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models.enums import MaterialRelationship, Verdict
from app.models.review import Review
from app.services.review_service import VERSIONED_FIELDS, _snapshot


def _fully_populated_review() -> Review:
    """Every versioned field set, with the type its column really produces.

    Not a Pydantic model and not a fixture from the API: the bug lives in the
    gap between what the database hands back and what JSON accepts, so the
    values here are the database's — `Decimal` for both numeric columns, real
    enum members for both enum columns.
    """
    review = Review()
    review.id = uuid.uuid4()
    review.title = "Solid powerbank, runs warm"
    review.discussion = "Weeks of use, and the only surprise is the heat."
    review.verdict = Verdict.it_depends
    review.verdict_explanation = "Depends how long you hold it."
    review.target_audience = "People who charge overnight."
    review.anti_target_audience = "People who want it in a pocket."
    review.star_rating = Decimal("3.5")
    review.pros = ["Charges fast", "Feels solid"]
    review.cons = ["Gets warm"]
    review.photo_url = "https://example.test/photo.jpg"
    review.price_paid = Decimal("1299.00")
    review.material_relationship = MaterialRelationship.free_or_discounted
    review.receipt_key = "receipts/whatever"
    review.created_at = datetime.now(UTC)
    return review


def test_the_snapshot_serialises():
    """The whole point. A failure here is a 500 on the composer's last step."""
    snapshot = _snapshot(_fully_populated_review())
    json.dumps(snapshot)  # must not raise


def test_every_versioned_field_is_in_the_snapshot():
    """A field dropped from the snapshot is edit history quietly going missing."""
    snapshot = _snapshot(_fully_populated_review())
    for field in VERSIONED_FIELDS:
        assert field in snapshot, f"{field} is versioned but not snapshotted"


def test_no_value_in_the_snapshot_is_a_type_json_cannot_hold():
    """Named types rather than a bare dumps(), so a failure says which field."""
    allowed = (str, int, float, bool, list, dict, type(None))
    snapshot = _snapshot(_fully_populated_review())
    for key, value in snapshot.items():
        assert isinstance(value, allowed), (
            f"snapshot[{key!r}] is {type(value).__name__}, which json cannot write"
        )
        assert not isinstance(value, Decimal), f"snapshot[{key!r}] is still a Decimal"


def test_the_rating_stays_a_number_and_keeps_its_half_step():
    """A version and the live review must compare equal, so 3.5 stays 3.5.

    Not a string: `star_rating` is served as a number everywhere else, and a
    snapshot that stringifies it makes the edit history incomparable with the
    review it is the history of.
    """
    snapshot = _snapshot(_fully_populated_review())
    assert snapshot["star_rating"] == 3.5
    assert isinstance(snapshot["star_rating"], float)
    assert json.loads(json.dumps(snapshot))["star_rating"] == 3.5


@pytest.mark.parametrize("rating", ["0", "0.5", "2.5", "5"])
def test_every_half_step_round_trips_through_json(rating: str):
    """0 to 5 in halves are all exact in binary; none may drift."""
    review = _fully_populated_review()
    review.star_rating = Decimal(rating)
    restored = json.loads(json.dumps(_snapshot(review)))
    assert restored["star_rating"] == float(rating)


def test_money_stays_a_string_so_it_cannot_acquire_a_binary_tail():
    """`price_paid` is money at two decimal places; float is the wrong shape."""
    snapshot = _snapshot(_fully_populated_review())
    assert snapshot["price_paid"] == "1299.00"
    assert isinstance(snapshot["price_paid"], str)


def test_the_enums_are_stored_as_their_values():
    snapshot = _snapshot(_fully_populated_review())
    assert snapshot["verdict"] == "it_depends"
    assert snapshot["material_relationship"] == "free_or_discounted"


def test_an_empty_review_still_serialises():
    """Every optional field null — the other end of the range."""
    review = Review()
    review.title = "Bare"
    review.discussion = "Nothing optional set."
    review.verdict = Verdict.hard_pass
    review.star_rating = Decimal("0")
    review.verdict_explanation = None
    review.target_audience = None
    review.anti_target_audience = None
    review.pros = None
    review.cons = None
    review.photo_url = None
    review.price_paid = None
    review.material_relationship = None
    review.receipt_key = None

    snapshot = _snapshot(review)
    json.dumps(snapshot)
    assert snapshot["star_rating"] == 0.0
    assert snapshot["price_paid"] is None
    assert snapshot["receipt_present"] is False


def test_the_receipt_key_never_reaches_the_snapshot():
    """Snapshots are public (GET /reviews/{id}/versions); the object key is not."""
    snapshot = _snapshot(_fully_populated_review())
    assert "receipt_key" not in snapshot
    assert snapshot["receipt_present"] is True
    assert "receipts/whatever" not in json.dumps(snapshot)
