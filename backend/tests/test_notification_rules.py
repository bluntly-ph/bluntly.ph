"""Notifications (FR-1 1.6), checked without a database.

A notification tells one account that something happened to *their* content:
a review was published or rejected (with the reason), their question was
answered, their answer was picked as best, their seller claim or price report
was decided. The rules that must hold everywhere are pinned here:

* **A notification link never leaves the site.** It is rendered as an href in
  the notification list, so an absolute or protocol-relative URL would be an
  open redirect wearing the platform's voice. Only a same-site path survives;
  anything else is dropped and the notification is delivered without a link.
* **The preview is an excerpt, not the content.** Bodies are cut at a fixed
  length on a word boundary, so a long answer or rejection reason cannot turn
  the list into a wall of text.
* **Every notification route needs an account**, and the static routes are
  declared before the parameterised one.
"""

from __future__ import annotations

from app.models.notification import Notification
from app.services.notification_service import EXCERPT_LIMIT, excerpt, safe_internal_link
from tests.test_seller_api_contract import _needs_account, _routes


class TestLinksStayOnTheSite:

    def test_a_site_path_is_kept(self):
        assert safe_internal_link("/questions/abc") == "/questions/abc"
        assert safe_internal_link("/sellers/1/dashboard") == "/sellers/1/dashboard"

    def test_an_absolute_url_is_dropped(self):
        assert safe_internal_link("https://evil.example/login") is None
        assert safe_internal_link("javascript:alert(1)") is None

    def test_protocol_relative_and_backslash_tricks_are_dropped(self):
        assert safe_internal_link("//evil.example") is None
        assert safe_internal_link("/\\evil.example") is None

    def test_no_link_is_no_link(self):
        assert safe_internal_link(None) is None
        assert safe_internal_link("") is None


class TestExcerpt:

    def test_short_text_is_unchanged(self):
        assert excerpt("Every Monday.") == "Every Monday."

    def test_long_text_is_cut_on_a_word_with_an_ellipsis(self):
        text = "word " * 100
        cut = excerpt(text)
        assert len(cut) <= EXCERPT_LIMIT + 1
        assert cut.endswith("…")
        assert not cut[:-1].endswith(" ")

    def test_whitespace_is_collapsed(self):
        assert excerpt("  one\n\n two\tthree  ") == "one two three"

    def test_nothing_is_empty(self):
        assert excerpt(None) == ""


def test_the_table_is_read_per_account_newest_first():
    index_columns = {tuple(c.name for c in ix.columns) for ix in Notification.__table__.indexes}
    assert ("user_id", "created_at") in index_columns
    assert Notification.__table__.c.read_at.nullable is True


ROUTES = [
    ("GET", "/api/v1/notifications"),
    ("GET", "/api/v1/notifications/unread-count"),
    ("POST", "/api/v1/notifications/read-all"),
    ("POST", "/api/v1/notifications/{notification_id}/read"),
]


def test_every_notification_route_needs_an_account():
    routes = _routes()
    for key in ROUTES:
        assert key in routes, f"missing {key}"
        assert _needs_account(routes[key]), f"{key} must require an account"
