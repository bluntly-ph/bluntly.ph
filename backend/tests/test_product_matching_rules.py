"""Duplicate product detection (FR-2 2.8), checked without a database.

BUG-020 found "Jisulife fan", "jisulife life9" and "JISULIFE Life 9" as three
products, splitting the reviews that should consolidate under one. Moderator
canonicalisation fixes a name after the fact; this stops the most mechanical
duplicates at submission: the same name typed differently, and the same
marketplace listing pasted with different tracking parameters.

The keys are deliberately conservative — only *identical after normalising*
counts as a match. "Jisulife Life 9" and "Jisulife Life9 Pro" stay distinct;
near-matches are the moderator's call, not an automatic merge that could put
one product's reviews on another.
"""

from __future__ import annotations

from app.services.product_matching import listing_key, name_key


class TestTheNameKey:

    def test_case_spacing_and_punctuation_do_not_make_a_new_product(self):
        assert name_key("JISULIFE Life 9") == name_key("  jisulife   life-9 ") == "jisulife life 9"

    def test_different_names_stay_different(self):
        assert name_key("Jisulife Life 9") != name_key("Jisulife Life 9 Pro")
        assert name_key("Jisulife Life9") != name_key("Jisulife Life 9")

    def test_only_ascii_letters_and_digits_survive(self):
        # The same rule runs in SQL (regexp [^a-z0-9]+), so both sides must agree
        # on what a non-ASCII letter becomes.
        assert name_key("Café Mug 500ml") == "caf mug 500ml"

    def test_a_name_with_nothing_left_has_no_key(self):
        assert name_key(" --- ") is None
        assert name_key("") is None


class TestTheListingKey:

    def test_tracking_parameters_and_fragments_are_ignored(self):
        assert (listing_key("https://shopee.ph/Jisulife-Fan-i.123.456?sp_atk=abc&xptdk=1#reviews")
                == "https://shopee.ph/jisulife-fan-i.123.456")

    def test_www_and_a_trailing_slash_are_ignored(self):
        assert (listing_key("https://www.lazada.com.ph/products/fan-i99.html/")
                == listing_key("https://lazada.com.ph/products/fan-i99.html"))

    def test_different_listings_stay_different(self):
        assert listing_key("https://shopee.ph/a-i.1.2") != listing_key("https://shopee.ph/a-i.1.3")

    def test_no_link_has_no_key(self):
        assert listing_key(None) is None
        assert listing_key("   ") is None
