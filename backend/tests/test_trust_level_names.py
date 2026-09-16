"""The trust level names, in stage order (FR-7; contract §9, matrix 7.8).

`users.trust_level_name` is a database expression over `trust_stage`, and it is
the only source of the name every trust badge shows. The frontend pins the same
six names in the same order (`tests/frontend/trust-display.test.mjs`), so a
rename on either side fails a test on that side rather than leaving the two to
disagree on screen.
"""

from __future__ import annotations

import re

from app.models.user import _TRUST_NAME_EXPR, TRUST_LEVEL_NAMES

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


def test_the_python_tuple_is_the_same_ladder():
    """`TRUST_LEVEL_NAMES` is derived from the expression, not retyped."""
    assert list(TRUST_LEVEL_NAMES) == EXPECTED


def test_the_progress_ladder_names_a_real_level_at_every_step():
    """Nothing can promise a member a stage that has no name."""
    from app.services.trust import TOP_STAGE, next_stage_progress

    for stage in range(TOP_STAGE):
        step = next_stage_progress(stage, review_count=0, verified_review_count=0)
        assert step is not None
        next_stage, have, needed = step
        assert next_stage == stage + 1
        assert TRUST_LEVEL_NAMES[next_stage] == EXPECTED[next_stage]
        assert have == 0 and needed >= 1
    assert next_stage_progress(TOP_STAGE, 100, 100) is None


def test_progress_never_overflows_the_bar():
    """Reviews done but stage not reached yet reads as full, not as 7 of 5."""
    from app.services.trust import next_stage_progress

    assert next_stage_progress(2, review_count=30, verified_review_count=7) == (3, 5, 5)
