"""Free-text search over questions, for the Questions tab on /search.

`GET /api/v1/questions` accepted a `q` parameter long before it meant anything —
the NUL-byte middleware test already exercised it — and silently ignored it, so
the Questions tab would have rendered the newest questions regardless of what was
typed. These tests pin the behaviour the tab depends on.

The product name is searchable as well as the wording, because someone typing
"jisulife" means the product at least as often as the phrasing of a question, and
the design puts the product name in the card's headline.
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import register_and_token, requires_db

pytestmark = requires_db


@pytest.fixture()
def asked(client):
    """A product with one question about it, plus an unrelated pair."""
    _, token, _ = register_and_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    marker = uuid.uuid4().hex[:8]

    def make(product_name: str, body: str) -> str:
        product = client.post(
            "/api/v1/products",
            json={"name": product_name, "source_url": f"https://shopee.ph/{marker}"},
            headers=headers,
        )
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]
        question = client.post(
            "/api/v1/questions",
            json={"product_id": product_id, "body": body, "directed_to": "buyers"},
            headers=headers,
        )
        assert question.status_code == 201, question.text
        return question.json()["id"]

    fan = make(f"Jisulife Handheld Fan {marker}", "Is this a good fan for studying?")
    kettle = make(f"Zojirushi Kettle {marker}", "Does the lid leak when pouring?")
    return {"marker": marker, "fan": fan, "kettle": kettle, "headers": headers}


def _ids(client, **params) -> list[str]:
    resp = client.get("/api/v1/questions", params={"limit": 100, **params})
    assert resp.status_code == 200, resp.text
    return [q["id"] for q in resp.json()]


def test_a_query_matches_the_product_name(client, asked):
    """The common case: the reader types the product, not the question."""
    found = _ids(client, q=f"Jisulife Handheld Fan {asked['marker']}")

    assert asked["fan"] in found
    assert asked["kettle"] not in found


def test_a_query_matches_the_question_wording(client, asked):
    found = _ids(client, q="lid leak")

    assert asked["kettle"] in found
    assert asked["fan"] not in found


def test_the_match_is_case_insensitive(client, asked):
    assert asked["fan"] in _ids(client, q=f"jisulife handheld fan {asked['marker']}")


def test_a_partial_term_still_matches(client, asked):
    """The tab searches as the reader types, so substrings have to work."""
    assert asked["fan"] in _ids(client, q="Jisulife")


def test_no_query_returns_questions_unfiltered(client, asked):
    """Absent `q`, the endpoint behaves exactly as it did before."""
    found = _ids(client)

    assert asked["fan"] in found
    assert asked["kettle"] in found


def test_whitespace_is_not_a_query(client, asked):
    """A blank query must not filter everything out."""
    found = _ids(client, q="   ")

    assert asked["fan"] in found
    assert asked["kettle"] in found


def test_a_query_that_matches_nothing_returns_nothing(client, asked):
    assert _ids(client, q=f"no-such-product-{asked['marker']}") == []


def test_a_query_composes_with_the_product_filter(client, asked):
    """`product_id` still narrows, and `q` narrows within it."""
    detail = client.get(f"/api/v1/questions/{asked['fan']}")
    assert detail.status_code == 200, detail.text
    product_id = detail.json()["product_id"]

    assert _ids(client, product_id=product_id, q="studying") == [asked["fan"]]
    assert _ids(client, product_id=product_id, q="lid leak") == []
