"""Anything that connects to decide something must be able to give up.

This fault was found five times in this codebase, in five different files, and
it looks harmless every time:

    with engine.connect() as conn: ...

A refused connection fails in milliseconds, so it behaves perfectly on a
developer machine and in CI. A port that *drops* packets instead — a firewall,
a paused database, a wrong host that resolves — never fails at all, and the
application engine has no timeout to stop it waiting. The symptom is never an
error. It is silence:

  * `tests/conftest.db_available` hung pytest during collection, before a
    single test ran, with no output to explain it.
  * `scripts.check_migration_safety` sat for over six minutes and printed
    nothing.
  * `scripts.check_invariants` — runbook step 11, meant to be pointed at
    production — retried fifteen times, ten seconds apart.
  * `scripts.wait_for_db` had a 30-attempt budget it could never spend, which
    is the precise failure it exists to prevent.
  * `scripts.db_check` exists to answer "can I reach the database" and could
    not answer.

So the rule is: a module that connects in order to *report* or *decide*
something gets its own engine with an explicit `connect_timeout`. The
application's engine is exempt — a request that cannot reach the database
should surface as a request error, not be second-guessed here.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]

#: Modules that connect to answer a question rather than to serve a request.
#: Each must bound its own connect.
DECIDERS = [
    BACKEND / "tests" / "conftest.py",
    BACKEND / "scripts" / "check_migration_safety.py",
    BACKEND / "scripts" / "check_invariants.py",
    BACKEND / "scripts" / "wait_for_db.py",
    BACKEND / "scripts" / "db_check.py",
]


def has_connect_timeout(source: str) -> bool:
    """True when the module passes connect_timeout to a create_engine call."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name != "create_engine":
            continue
        for keyword in node.keywords:
            if keyword.arg == "connect_args" and "connect_timeout" in ast.unparse(
                keyword.value
            ):
                return True
    return False


@pytest.mark.parametrize("path", DECIDERS, ids=lambda p: p.name)
def test_it_builds_its_own_bounded_engine(path):
    source = path.read_text(encoding="utf-8")
    assert has_connect_timeout(source), (
        f"{path.name} connects without a connect_timeout. A refused connection "
        f"fails fast and a dropped one never fails — this module would hang "
        f"silently rather than report.")


@pytest.mark.parametrize("path", DECIDERS, ids=lambda p: p.name)
def test_it_does_not_borrow_the_application_engine(path):
    """`from app.db.session import engine` brings the missing timeout with it."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "app.db.session":
            imported = {alias.name for alias in node.names}
            assert "engine" not in imported, (
                f"{path.name} imports the application engine, which has no "
                f"connect timeout — build a bounded one instead")


def test_check_invariants_proves_the_connection_once():
    """Fifteen checks that each swallow their own errors retry fifteen times.

    Catching per check is right — one bad query must not hide the rest — but it
    turns an unreachable database into fifteen sequential timeouts, which reads
    as a hang.
    """
    source = (BACKEND / "scripts" / "check_invariants.py").read_text(encoding="utf-8")
    assert "cannot reach the database" in source, (
        "check_invariants no longer proves the connection before running its "
        "checks, so an unreachable database is retried once per invariant")
