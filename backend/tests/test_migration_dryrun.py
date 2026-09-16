"""Every migration's `upgrade()` and `downgrade()` must at least RUN.

The only thing that executes a migration is CI's isolated-database job, and it
takes about two hours. So a plain mistake inside a migration body — a name that
was never imported, a type referenced through the wrong module — is invisible
until the last step of the longest job in the pipeline.

That is not hypothetical. `0049` was written with
`sa.dialects.postgresql.UUID(as_uuid=True)`, which raises `AttributeError:
module 'sqlalchemy.dialects' has no attribute 'postgresql'` — `sqlalchemy` does
not re-export its dialect submodules. It passed import, ruff and the whole unit
suite, because nothing called the function.

This calls it. `alembic.op` is replaced with a recorder for the whole of the
import and the call, so every expression in the body is evaluated and nothing is
executed: no database, no connection, no dependence on migration order. It says
nothing about whether the SQL is *right* — the isolated-database job still owns
that — only that the Python runs.

Not marked `requires_db` on purpose: the point is to fail in the fast job.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"

#: Migrations whose `downgrade()` is deliberately empty, with the reason each
#: one gives for it. Listed rather than inferred: "this migration does nothing"
#: and "this migration silently did nothing" look identical from here, and only
#: the first is acceptable.
DELIBERATE_NO_OP_DOWNGRADES = {
    "0025_receipt_view_audit": "dropping an enum label would risk the audit trail",
    "0029_revoke_postgrest_access": "re-granting removed access is not a rollback",
    "0040_role_admin_audit_enum": "audit rows may use the labels; rebuilding destroys history",
    "0027_normalize_categories": "renamed category values; there is nothing to put back",
}


class _Recorder:
    """Stands in for `alembic.op`. Records, returns a stub, executes nothing."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str):
        def call(*args, **kwargs):
            self.calls.append(name)
            if name == "get_bind":
                return _Bind()
            return _Stub()

        return call


class _Stub:
    """A return value that survives being used as a context manager or attribute.

    `op.batch_alter_table(...)` is used with `with`, and its handle is called
    like `op` itself — so whatever a recorded op returns has to behave the same
    way rather than being None.
    """

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __getattr__(self, name: str):
        def call(*args, **kwargs):
            return _Stub()

        return call


class _Result:
    """An empty result set, for a data migration that reads what it wrote.

    `0027` checks `result.rowcount` and iterates a diagnostic SELECT, so a bind
    that answers None is not a stand-in for a connection — it is a different
    kind of failure that would be reported as if the migration were broken.
    Zero rows is the honest answer here: nothing was actually executed.
    """

    rowcount = 0

    def scalars(self):
        return self

    def all(self) -> list:
        return []

    def fetchall(self) -> list:
        return []

    def __iter__(self):
        return iter(())


class _Bind:
    """What `Enum.create(bind, checkfirst=True)` and `op.get_bind()` return.

    A REAL postgresql dialect: SQLAlchemy's type machinery reaches into it
    (`_type_memos`, `has_type`), and a namespace stub only proves the stub is
    wrong. `has_type` answers False so `checkfirst=True` takes the create path,
    which is the one production will take.
    """

    dialect = postgresql.dialect()

    def has_type(self, *args, **kwargs) -> bool:
        return False

    def execute(self, *args, **kwargs) -> _Result:
        return _Result()

    def __getattr__(self, name: str):
        def call(*args, **kwargs):
            return None

        return call


def _migration_files() -> list[Path]:
    return sorted(p for p in VERSIONS.glob("*.py") if not p.name.startswith("__"))


@contextmanager
def _fake_alembic(recorder: _Recorder):
    """Replace `alembic` for the import AND the call, then put the real one back.

    Both, because a migration may import inside its own function — `0027` does
    `from alembic import context` in the middle of `upgrade()` — and a fake that
    is already gone by then hands it the real EnvironmentContext proxy, which
    raises for want of a live migration environment.
    """
    saved = sys.modules.get("alembic")
    fake = types.ModuleType("alembic")
    fake.op = recorder
    # Offline mode is the branch that writes SQL to a file instead of running
    # it. Answering False takes the path production takes.
    fake.context = types.SimpleNamespace(is_offline_mode=lambda: False)
    sys.modules["alembic"] = fake
    try:
        yield
    finally:
        # Every other test in the session imports the real alembic; leaving the
        # fake in place would be a far worse bug than the one this catches.
        if saved is not None:
            sys.modules["alembic"] = saved
        else:
            sys.modules.pop("alembic", None)


def test_there_are_migrations_to_check():
    """A glob that silently matches nothing would pass every test below."""
    assert len(_migration_files()) > 40


def test_the_no_op_list_names_migrations_that_exist():
    """A stale exemption is how a real empty downgrade gets waved through."""
    stems = {p.stem for p in _migration_files()}
    assert set(DELIBERATE_NO_OP_DOWNGRADES) <= stems


@pytest.mark.parametrize("path", _migration_files(), ids=lambda p: p.stem)
@pytest.mark.parametrize("direction", ["upgrade", "downgrade"])
def test_migration_body_runs(path: Path, direction: str):
    recorder = _Recorder()

    with _fake_alembic(recorder):
        spec = importlib.util.spec_from_file_location(f"_dryrun_{path.stem}", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        run = getattr(module, direction, None)
        assert callable(run), f"{path.name} has no {direction}()"
        run()

    if direction == "downgrade" and path.stem in DELIBERATE_NO_OP_DOWNGRADES:
        assert not recorder.calls, (
            f"{path.stem} is listed as a deliberate no-op downgrade "
            f"({DELIBERATE_NO_OP_DOWNGRADES[path.stem]}) but now does something — "
            f"take it off the list rather than leaving the list wrong"
        )
        return

    assert recorder.calls, (
        f"{path.name} {direction}() recorded no operation at all — either it is "
        f"empty, or it is doing its work somewhere this cannot see"
    )
