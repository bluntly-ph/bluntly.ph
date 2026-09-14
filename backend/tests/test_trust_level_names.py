"""The trust level names, in stage order (FR-7; contract §9, matrix 7.8).

`users.trust_level_name` is a database expression over `trust_stage`, and it is
the only source of the name every trust badge shows. The frontend pins the same
six names in the same order (`tests/frontend/trust-display.test.mjs`), so a
rename on either side fails a test on that side rather than leaving the two to
disagree on screen.
"""

from __future__ import annotations

import re

from app.models.user import _TRUST_NAME_EXPR

EXPECTED = ["Newcomer", "Contributor", "Verified Buyer", "Established Reviewer",
            "Trusted Reviewer", "Community Expert"]


def test_the_six_levels_are_named_in_stage_order():
    pairs = re.findall(r"WHEN (\d) THEN '([^']+)'", _TRUST_NAME_EXPR)
    assert [int(stage) for stage, _ in pairs] == [0, 1, 2, 3, 4, 5]
    assert [name for _, name in pairs] == EXPECTED


def test_verified_buyer_is_the_first_verified_review():
    # The onboarding copy promises this; determine_stage is what decides it.
    from app.services.trust import determine_stage

    assert determine_stage(review_count=1, verified_review_count=0, helpfulness_ratio=0,
                           best_answer_count=0, strikes=0, months_active=0) == 1
    assert determine_stage(review_count=1, verified_review_count=1, helpfulness_ratio=0,
                           best_answer_count=0, strikes=0, months_active=0) == 2
