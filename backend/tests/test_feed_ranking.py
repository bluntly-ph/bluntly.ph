"""The /feed ranking rules, as pure functions.

`diversify` and `prioritise_interests` decide what a reader sees when they open
the app with no search in mind, so they are the two rules most worth pinning.
Both are pure — no database, no fixtures — which is the reason they were
extracted from the endpoint in the first place.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.services.review_service import diversify, prioritise_interests


def _row(author: str | None, product: str, category: str | None = None):
    """A (review, author, product) triple shaped like list_feed's output."""
    return (
        SimpleNamespace(id=uuid.uuid4(), product_id=product),
        SimpleNamespace(id=author) if author is not None else None,
        SimpleNamespace(id=product, category=category),
    )


class TestDiversity:
    def test_one_author_does_not_crowd_out_the_others(self):
        """The cap binds when there is competition for the slots.

        Six reviews by one person rank above four by other people. Without a
        cap the whole page is one voice; with it, ann keeps the top two and the
        rest of the page belongs to everyone else.
        """
        rows = ([_row("ann", f"a{i}") for i in range(6)]
                + [_row(f"u{i}", f"b{i}") for i in range(4)])
        out = diversify(rows, limit=4)
        assert sum(1 for _, a, _ in out if a.id == "ann") == 2
        assert len({a.id for _, a, _ in out}) == 3, "three distinct voices in four slots"

    def test_one_product_cannot_take_the_whole_feed(self):
        rows = [_row(f"u{i}", "same-product") for i in range(6)]
        out = diversify(rows, limit=4, max_per_product=2)
        first_two = out[:2]
        assert all(p.id == "same-product" for _, _, p in first_two)

    def test_ranking_order_is_preserved(self):
        """Diversity thins; it must never re-sort."""
        rows = [_row(f"u{i}", f"p{i}") for i in range(5)]
        out = diversify(rows, limit=5)
        assert [r.id for r, _, _ in out] == [r.id for r, _, _ in rows]

    def test_a_small_corpus_still_fills_the_page(self):
        """Strict caps on fifteen reviews would return four. They must not."""
        rows = [_row("ann", "one") for _ in range(6)]
        out = diversify(rows, limit=5)
        assert len(out) == 5, "capped rows are appended, not discarded"

    def test_an_anonymous_author_does_not_crash_the_cap(self):
        rows = [_row(None, f"p{i}") for i in range(3)]
        assert len(diversify(rows, limit=3)) == 3


class TestInterests:
    def test_chosen_categories_come_first(self):
        rows = [_row("a", "p1", "food"), _row("b", "p2", "gaming"),
                _row("c", "p3", "food")]
        out = prioritise_interests(rows, ["gaming"])
        assert out[0][2].category == "gaming"

    def test_nothing_is_removed(self):
        """A reader with one matching category still gets a full feed."""
        rows = [_row("a", "p1", "food"), _row("b", "p2", "gaming")]
        assert len(prioritise_interests(rows, ["gaming"])) == 2

    def test_no_interests_is_a_no_op(self):
        rows = [_row("a", "p1", "food"), _row("b", "p2", "gaming")]
        for empty in (None, []):
            assert prioritise_interests(rows, empty) == rows

    def test_an_unknown_interest_does_not_empty_the_feed(self):
        rows = [_row("a", "p1", "food")]
        assert len(prioritise_interests(rows, ["not-a-category"])) == 1

    def test_alias_spellings_still_match(self):
        """`electronics` rows predate the vocabulary; the reader picked
        `electronics-tech`. They are the same shelf."""
        rows = [_row("a", "p1", "electronics"), _row("b", "p2", "food")]
        out = prioritise_interests(rows, ["electronics-tech"])
        assert out[0][2].category == "electronics"
