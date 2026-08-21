"""You cannot pay yourself for answering your own question.

Q&A was the one feature that did not check this. Comment votes, review votes,
request up-votes and reports all refuse self-dealing explicitly; `create_answer`
and `mark_best_answer` did not — so asking a question and answering it a second
later awarded the `first_responder` badge, and the asker could then mark their
own answer best for a second one. Repeatable, one new question at a time.

Badges do not feed the trust score — stages award badges, not the reverse — so
this inflated displayed credibility rather than ranking. On a platform whose
whole premise is trustworthiness, that is the part that matters.

Answering your own question is still allowed. Somebody who finds the answer and
comes back to share it is doing what the board is for; they just do not get
paid for it.

The behaviour needs a database, so these tests assert the rule at the point it
is decided. The DB-backed versions live in `test_qa_api.py` and skip without a
Postgres, which is the condition that let this sit unnoticed.
"""

from __future__ import annotations

import inspect
import re

from app.services import qa_service


def source_of(fn) -> str:
    return inspect.getsource(fn)


class TestTheFirstResponderBadge:

    def test_create_answer_excludes_the_asker(self):
        src = source_of(qa_service.create_answer)
        assert "answering_own" in src, (
            "create_answer no longer distinguishes the asker, so asking and "
            "immediately answering awards the first-responder badge")
        assert re.search(r"is_first\s*=.*not answering_own", src), (
            "is_first no longer excludes the asker")

    def test_the_comparison_is_against_the_asker(self):
        src = source_of(qa_service.create_answer)
        assert re.search(r"answering_own\s*=\s*responder_id == question\.asker_id", src)


class TestPickingTheBestAnswer:

    def test_the_asker_cannot_pick_their_own(self):
        src = source_of(qa_service.mark_best_answer)
        assert "cannot_pick_own_answer" in src, (
            "mark_best_answer no longer refuses the asker's own answer")

    def test_it_still_refuses_a_stranger(self):
        """The pre-existing guard must survive the new one."""
        assert "not_question_owner" in source_of(qa_service.mark_best_answer)

    def test_it_still_refuses_an_answer_from_another_question(self):
        src = source_of(qa_service.mark_best_answer)
        assert "answer.question_id != question.id" in src


class TestEveryInteractionRefusesSelfDealing:
    """The generalised rule, so the next feature does not miss it."""

    EXPECTED = {
        "comment_service": "your own comment",
        "request_service": "own request",
        "vote_service": "your own review",
        "qa_service": "cannot_pick_own_answer",
    }

    def test_each_service_has_its_guard(self):
        import pathlib
        services = pathlib.Path(qa_service.__file__).parent
        missing = []
        for name, marker in self.EXPECTED.items():
            src = (services / f"{name}.py").read_text(encoding="utf-8")
            if marker not in src:
                missing.append(f"{name} is missing its self-dealing guard ({marker!r})")
        assert not missing, missing
