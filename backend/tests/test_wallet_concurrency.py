"""Money must not be moved by read-modify-write.

    user.wallet_balance = user.wallet_balance + x

reads, adds and writes in three steps. Two concurrent adjustments to one wallet
both read the same starting balance, and the second write discards the first.
Every path that moved money did it this way: the payout reserve and its two
refunds, the commission split, a contract buyout, an Honesty Fund distribution.

Three of those are credits, so the lost update costs a real person money they
earned, and nothing reports it — the balance is simply lower than the sum of
its inflows. It needs no attacker: the payout scheduler and a moderator
approving a commission touch the same wallets by design.

The state guards had the same shape. "Only a scheduled payout can be cancelled"
reads as a state machine, but read outside a lock two callers both see
`scheduled`, both pass, and both refund.

The static tests below run anywhere. The concurrency tests need a real database
and are skipped until one exists.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from tests.conftest import requires_db

SERVICES = pathlib.Path(__file__).resolve().parents[1] / "app" / "services"

# Transitions that guard on current state, and so must hold a row lock before
# they read it. Keyed by the service that owns them.
#
# contract_service turned up in exactly the condition payout_service had been
# in: accept_buyout read `status`, decided, credited a wallet, then wrote the
# new status — so two concurrent accepts both saw `active`, both passed the
# guard, and both paid out the buyout amount for one contract.
GUARDED_TRANSITIONS = {
    "payout_service": ("mark_paid", "mark_failed", "cancel", "retry"),
    "contract_service": (
        "set_auto_renew", "offer_buyout", "accept_buyout", "reject_buyout",
    ),
}

#: The object each service's `_locked` helper re-reads.
LOCK_SUBJECT = {"payout_service": "payout", "contract_service": "contract"}


class TestNoServiceDoesWalletArithmeticInPython:

    def test_no_read_modify_write_on_a_balance(self):
        offenders = []
        pattern = re.compile(
            r"\.wallet_balance\s*=\s*.*\.wallet_balance\s*[-+]|"
            r"\.wallet_balance\s*[-+]=")
        for f in SERVICES.glob("*.py"):
            if f.name == "wallet.py":
                continue  # its docstring quotes the anti-pattern to explain it
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if line.lstrip().startswith(("#", '"', "'")):
                    continue
                if pattern.search(line):
                    offenders.append(f"{f.name}:{i}")
        assert not offenders, (
            f"{offenders} adjust a wallet in Python. Use wallet.adjust(), which "
            f"does the addition in one UPDATE so concurrent changes compose.")

    def test_every_money_service_goes_through_the_helper(self):
        for name in ("payout_service", "commission_service",
                     "contract_service", "honesty_fund_service"):
            src = (SERVICES / f"{name}.py").read_text(encoding="utf-8")
            assert "wallet.adjust(" in src, f"{name} moves money another way"


class TestGuardedTransitionsTakeARowLock:

    @pytest.mark.parametrize("service", sorted(GUARDED_TRANSITIONS))
    def test_each_transition_locks_before_it_checks(self, service):
        src = (SERVICES / f"{service}.py").read_text(encoding="utf-8")
        subject = LOCK_SUBJECT[service]
        for fn in GUARDED_TRANSITIONS[service]:
            m = re.search(rf"^def {fn}\([\s\S]*?(?=\n(?:def |\Z))", src, re.M)
            assert m, f"{service}.{fn} not found"
            body = m.group(0)
            lock = body.find(f"_locked(db, {subject})")
            check = body.find(f"{subject}.status")
            assert lock != -1, (
                f"{service}.{fn} checks state without locking the row first")
            if check != -1:
                assert lock < check, (
                    f"{service}.{fn} reads {subject}.status before taking the "
                    f"lock, so two callers can both pass the guard")

    @pytest.mark.parametrize("service", sorted(GUARDED_TRANSITIONS))
    def test_the_lock_refreshes_the_identity_map(self, service):
        """Without populate_existing the lock hands back the stale instance."""
        src = (SERVICES / f"{service}.py").read_text(encoding="utf-8")
        m = re.search(r"def _locked\([\s\S]*?(?=\n\ndef )", src)
        assert m, f"{service} has no _locked helper"
        assert "with_for_update()" in m.group(0)
        assert "populate_existing" in m.group(0), (
            f"{service}._locked takes the lock but returns the cached object, "
            f"so the state it re-checks is the one it already had")

    def test_no_money_path_checks_state_without_a_lock(self):
        """The generalised form: any service that credits a wallet after
        testing a status must own a `_locked` helper.

        This is what would have caught contract_service, which had the same
        shape as payout_service and none of the protection.
        """
        for path in SERVICES.glob("*_service.py"):
            src = path.read_text(encoding="utf-8")
            if "wallet.adjust(" not in src:
                continue
            if ".status !=" not in src and ".status not in" not in src:
                continue
            assert "def _locked(" in src, (
                f"{path.name} credits a wallet after testing a status but has "
                f"no _locked helper, so two callers can both pass the guard")


@requires_db
class TestConcurrentMoneyMovesCompose:
    """The behaviour the static tests stand in for, once a database exists."""

    def test_two_credits_to_one_wallet_both_land(self, db):
        from decimal import Decimal

        from app.services import wallet
        from tests.conftest import make_user

        user = make_user(db)
        start = user.wallet_balance
        wallet.adjust(db, user.id, Decimal("10.00"))
        wallet.adjust(db, user.id, Decimal("15.00"))
        db.commit()
        db.refresh(user)
        assert user.wallet_balance == start + Decimal("25.00")

    def test_a_debit_below_zero_is_refused_by_the_database(self, db):
        from decimal import Decimal

        from sqlalchemy.exc import IntegrityError

        from app.services import wallet
        from tests.conftest import make_user

        user = make_user(db)
        with pytest.raises(IntegrityError):
            wallet.adjust(db, user.id, -(user.wallet_balance + Decimal("1.00")))
            db.flush()
