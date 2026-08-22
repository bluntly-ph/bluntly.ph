"""The transition matrix: what a status change is allowed to do to money.

Reports overlap, so a second import of the same order is a state change, not a
duplicate. These pin which changes are legal and which move money — the rules
that decide whether a reviewer is paid once, twice, or not at all.
"""

from __future__ import annotations

import itertools

from app.models.enums import AffiliateTxStatus as S
from app.services.affiliate_transitions import Effect, evaluate


class TestFirstSighting:
    def test_a_new_completed_row_recognises_once(self):
        t = evaluate(None, S.completed)
        assert t.allowed and t.effect is Effect.recognise

    def test_a_new_pending_row_recognises_nothing(self):
        assert evaluate(None, S.pending).effect is Effect.none

    def test_a_new_cancelled_or_returned_row_recognises_nothing(self):
        assert evaluate(None, S.cancelled).effect is Effect.none
        assert evaluate(None, S.returned).effect is Effect.none


class TestTheOrdinaryLifecycle:
    def test_pending_to_completed_finalises(self):
        assert evaluate(S.pending, S.completed).effect is Effect.recognise

    def test_pending_to_cancelled_only_drops_pending(self):
        t = evaluate(S.pending, S.cancelled)
        assert t.effect is Effect.drop_pending
        assert t.effect is not Effect.reverse, "nothing was earned to reverse"

    def test_completed_to_returned_reverses(self):
        assert evaluate(S.completed, S.returned).effect is Effect.reverse

    def test_completed_to_cancelled_reverses(self):
        """A provider withdrawing a recognised sale is a reversal, not a drop."""
        assert evaluate(S.completed, S.cancelled).effect is Effect.reverse


class TestRepeatsDoNotMoveMoneyTwice:
    """The single most expensive class of bug in an importer."""

    def test_completed_seen_again_does_nothing(self):
        assert evaluate(S.completed, S.completed).effect is Effect.none

    def test_returned_seen_again_does_not_reverse_twice(self):
        assert evaluate(S.returned, S.returned).effect is Effect.none

    def test_pending_seen_again_does_nothing(self):
        assert evaluate(S.pending, S.pending).effect is Effect.none

    def test_cancelled_seen_again_does_nothing(self):
        assert evaluate(S.cancelled, S.cancelled).effect is Effect.none

    def test_every_self_transition_is_inert(self):
        for status in S:
            assert evaluate(status, status).effect is Effect.none, status


class TestProviderCorrections:
    def test_a_reinstated_cancellation_recognises_for_the_first_time(self):
        """Nothing was earned while cancelled, so this credits once, not twice."""
        assert evaluate(S.cancelled, S.completed).effect is Effect.recognise

    def test_a_reinstated_return_credits_again(self):
        assert evaluate(S.returned, S.completed).effect is Effect.recognise

    def test_a_settled_return_cannot_go_back_to_pending(self):
        t = evaluate(S.returned, S.pending)
        assert not t.allowed

    def test_un_finalising_a_completed_sale_reverses_it(self):
        """Money recognised against a sale the provider no longer calls final
        must not sit in a wallet on the strength of a changed report."""
        assert evaluate(S.completed, S.pending).effect is Effect.reverse


class TestTheMatrixIsTotal:
    def test_every_pair_has_a_decision(self):
        """No pair may fall through to an accidental default."""
        for a, b in itertools.product(S, S):
            t = evaluate(a, b)
            assert isinstance(t.allowed, bool)
            assert t.reason, f"{a.value}->{b.value} has no stated reason"

    def test_nothing_recognises_and_reverses_at_once(self):
        for a, b in itertools.product(S, S):
            assert evaluate(a, b).effect in set(Effect)

    def test_only_transitions_into_completed_can_recognise(self):
        for a, b in itertools.product(S, S):
            if evaluate(a, b).effect is Effect.recognise:
                assert b is S.completed, f"{a.value}->{b.value} recognises money"

    def test_reversal_only_ever_leaves_completed(self):
        for a, b in itertools.product(S, S):
            if evaluate(a, b).effect is Effect.reverse:
                assert a is S.completed, f"{a.value}->{b.value} reverses money"
