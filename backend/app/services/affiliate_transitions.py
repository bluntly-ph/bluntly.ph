"""What a change of canonical status is allowed to do to money.

Reports overlap. An order that is `pending` in June's export is `completed` in
July's, and one that was `completed` can come back `returned` months later. So a
second import is not a duplicate to be discarded — it is a state change to be
applied exactly once.

This module owns two questions and nothing else:

* is this transition legal?
* what financial effect does it have?

It is pure. No database, no session, no clock. The caller performs the effect
inside its own transaction, which is what keeps the locking guarantees in
`wallet` and `payout_service` intact.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.models.enums import AffiliateTxStatus as S


class Effect(str, Enum):
    """What the ledger must do about a transition."""

    none = "none"
    #: Recognise commission for the first time: split it, credit the wallet.
    recognise = "recognise"
    #: Undo a previously recognised commission with a *new* opposing entry.
    #: Never by editing the original — that destroys the audit trail.
    reverse = "reverse"
    #: The transaction never earned anything; drop it out of pending totals.
    drop_pending = "drop_pending"


@dataclass(frozen=True)
class Transition:
    allowed: bool
    effect: Effect
    reason: str


#: The transition matrix, keyed (from, to).
#:
#: Absent pairs are refused rather than silently ignored, because an unlisted
#: transition means the provider did something we have not reasoned about, and
#: guessing at it moves money.
_MATRIX: dict[tuple[S, S], Transition] = {
    # --- from pending -------------------------------------------------------
    (S.pending, S.pending): Transition(True, Effect.none, "unchanged"),
    (S.pending, S.completed): Transition(
        True, Effect.recognise, "provider finalised the sale"),
    (S.pending, S.cancelled): Transition(
        True, Effect.drop_pending, "died before finality; nothing was earned"),
    # Rare but real: a provider can skip straight to a return if the order
    # completed and reversed between two of our imports. Nothing was recognised
    # while it was pending, so there is nothing to reverse — it simply leaves
    # pending. Recording it as `returned` rather than `cancelled` keeps the
    # provider's own account of what happened.
    (S.pending, S.returned): Transition(
        True, Effect.drop_pending, "returned before we recognised it"),

    # --- from completed -----------------------------------------------------
    (S.completed, S.completed): Transition(
        True, Effect.none, "unchanged; must not credit twice"),
    (S.completed, S.returned): Transition(
        True, Effect.reverse, "buyer returned a sale we had recognised"),
    (S.completed, S.cancelled): Transition(
        True, Effect.reverse, "provider withdrew a sale we had recognised"),
    # A completed sale going back to pending is the provider contradicting
    # itself. Allowed, because Shopee and Lazada both restate rows, but it must
    # reverse: money recognised against a sale that is no longer final cannot
    # stay in a wallet on the strength of a report that has changed its mind.
    (S.completed, S.pending): Transition(
        True, Effect.reverse, "provider un-finalised a recognised sale"),

    # --- from cancelled -----------------------------------------------------
    (S.cancelled, S.cancelled): Transition(True, Effect.none, "unchanged"),
    # Providers do correct mistakes. Nothing was earned while cancelled, so
    # this recognises for the first time rather than double-crediting.
    (S.cancelled, S.completed): Transition(
        True, Effect.recognise, "provider reinstated a cancelled sale"),
    (S.cancelled, S.pending): Transition(
        True, Effect.none, "provider reopened it; still nothing earned"),
    (S.cancelled, S.returned): Transition(
        True, Effect.none, "already earning nothing; return changes no money"),

    # --- from returned ------------------------------------------------------
    (S.returned, S.returned): Transition(
        True, Effect.none, "unchanged; must not reverse twice"),
    # A return being undone is the one transition that can put money back. It is
    # allowed because providers do reinstate wrongly-returned orders, and it
    # goes through `recognise` so the credit is a new, dated ledger entry rather
    # than an un-deletion of the reversal.
    (S.returned, S.completed): Transition(
        True, Effect.recognise, "provider reinstated a returned sale"),
    (S.returned, S.pending): Transition(
        False, Effect.none, "a settled return cannot become pending again"),
    (S.returned, S.cancelled): Transition(
        True, Effect.none, "already reversed; reclassification only"),
}


def evaluate(current: S | None, incoming: S) -> Transition:
    """What should happen when `current` becomes `incoming`.

    `current is None` is a first sighting: the row has never been imported.
    Only a `completed` first sighting recognises money — everything else is
    recorded and waits, which is the conservative direction.
    """
    if current is None:
        if incoming is S.completed:
            return Transition(True, Effect.recognise, "new transaction, already final")
        return Transition(True, Effect.none, f"new transaction, {incoming.value}")

    known = _MATRIX.get((current, incoming))
    if known is None:
        return Transition(
            False, Effect.none,
            f"unlisted transition {current.value} -> {incoming.value}")
    return known
