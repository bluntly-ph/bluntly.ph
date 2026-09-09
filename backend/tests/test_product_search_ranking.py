"""Product search returns the closest match first (QA-001).

`GET /api/v1/products?q=` casts a deliberately wide net — `ilike %term%`, so a
reviewer who types "anker" still finds "Anker 737 Power Bank (24000mAh)" and one
who types part of a model number still finds the model. That width is wanted.

What was wrong was the ORDER. The net was sorted by `created_at DESC`, so the
newest row won no matter how badly it matched: searching "ma" put a product
somebody had just submitted above every genuine match, with "10000mAh" and
"MacBook" beneath it in arbitrary order. On the review composer's "What did you
buy?" step that reads as a broken search, and it is the step where a reviewer
either finds their product or gives up and creates a duplicate of it.

The ranking is explainable on purpose: exact name, then name-starts-with, then a
word inside the name starting with the term, then a bare substring; shorter
names break ties, and only then does recency matter.
"""

from __future__ import annotations

import uuid

from app.models.product import Product
from tests.conftest import requires_db


def _product(db, name: str):
    product = Product(canonical_name=name)
    db.add(product)
    db.flush()
    return product


@requires_db
def test_search_ranks_the_closest_name_first(db, client):
    """Exact, then prefix, then word-start, then "it is in there somewhere"."""
    marker = uuid.uuid4().hex[:6]
    # Created newest-first in the order that would WIN under the old sort, so a
    # pass here cannot be recency accidentally agreeing with relevance.
    _product(db, f"Aukey 10000m{marker} Power Bank")   # substring only
    _product(db, f"Power Bank m{marker} Edition")      # word-start
    _product(db, f"m{marker} Air M2 (13-inch)")        # name prefix
    _product(db, f"m{marker}")                         # exact
    db.commit()

    body = client.get(f"/api/v1/products?q=m{marker}&limit=10").json()
    names = [row["canonical_name"] for row in body]

    assert names[0] == f"m{marker}", "the exact name is not first"
    assert names[1] == f"m{marker} Air M2 (13-inch)", "the prefix match is not second"
    assert names[2] == f"Power Bank m{marker} Edition", "the word-start match is not third"
    assert names[3] == f"Aukey 10000m{marker} Power Bank", "the substring match is not last"


@requires_db
def test_a_newer_worse_match_does_not_outrank_an_older_better_one(db, client):
    """The regression itself: recency used to be the only sort key."""
    marker = uuid.uuid4().hex[:6]
    exact = _product(db, f"k{marker}")
    db.commit()
    # Created AFTER the exact match, and matching only as a substring.
    _product(db, f"Something With k{marker} Buried Inside It")
    db.commit()

    body = client.get(f"/api/v1/products?q=k{marker}&limit=10").json()

    assert body[0]["id"] == str(exact.id)


@requires_db
def test_an_unfiltered_listing_is_still_newest_first(db, client):
    """No search term, no relevance to rank by — the catalogue listing keeps
    its own order rather than silently changing shape."""
    newest = _product(db, f"Listing fixture {uuid.uuid4().hex[:8]}")
    db.commit()

    body = client.get("/api/v1/products?limit=5").json()

    assert body[0]["id"] == str(newest.id)
