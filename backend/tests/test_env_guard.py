"""The production guard must refuse production and allow a declared test target.

These pin the behaviour that stops a repeat of 2026-08-19, when the full suite
ran against the live database and created hundreds of fixture reviews.

Every test drives the guard through a temporary env-file layout rather than the
real one, so the assertions hold regardless of what the developer running them
has in `.env`.
"""

from __future__ import annotations

import pytest

from app.core import env_guard
from app.core.env_guard import ProductionTargetError

PROD_REF = env_guard.PRODUCTION_PROJECT_REF


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Point the guard at a throwaway env-file layout and a clean environment."""
    root_env = tmp_path / ".env"
    backend_env = tmp_path / "backend.env"
    test_env = tmp_path / ".env.test"
    for path in (root_env, backend_env, test_env):
        path.write_text("", encoding="utf-8")
    # Mirrors production exactly: these are what Settings reads, in Settings'
    # order, with .env.test LAST so it wins.
    monkeypatch.setattr(env_guard, "_TEST_ENV_FILE", str(test_env))
    monkeypatch.setattr(env_guard, "_settings_env_files",
                        lambda: (str(root_env), str(backend_env), str(test_env)))
    # The real `Settings` is pointed wherever this developer's config points;
    # these tests are about the guard's own resolution, so silence the
    # already-imported-config shortcut and let the file layout above decide.
    monkeypatch.setattr(env_guard, "_resolved_connection", lambda: "")
    for key in env_guard._KEYS + (env_guard.TEST_ENV_MARKER,):
        monkeypatch.delenv(key, raising=False)

    def write(which, **values):
        target = {"root": root_env, "backend": backend_env, "test": test_env}[which]
        target.write_text(
            "\n".join(f"{k}={v}" for k, v in values.items()), encoding="utf-8")

    return write


def test_production_project_ref_is_detected(env):
    env("root", SUPABASE_URL=f"https://{PROD_REF}.supabase.co")
    signals = env_guard.production_signals()
    assert signals, "the production project ref must be detected"
    with pytest.raises(ProductionTargetError):
        env_guard.require_non_production("pytest")


def test_production_site_host_is_detected(env):
    env("root", NEXT_PUBLIC_SITE_URL="https://www.bluntly.ph")
    assert env_guard.production_signals()


def test_app_env_production_is_detected(env):
    env("root", APP_ENV="production")
    assert "APP_ENV=production" in env_guard.production_signals()


def test_credentials_in_a_FILE_are_detected_not_just_the_environment(env):
    """The bug that nearly made this guard decorative.

    Production credentials live in the repo-root .env file and are never
    exported. A guard reading os.environ alone saw nothing, reported
    "unrecognised", and would have let anyone who set the test marker run
    straight into production.
    """
    env("root", SUPABASE_CONNECTION_STRING=f"postgres://u:p@db.{PROD_REF}.supabase.co:5432/postgres")
    env("test", BLUNTLY_TEST_ENV="1", APP_ENV="test")
    env_guard.load_test_env()
    # Marker present AND production connection present -> still refused.
    assert env_guard.is_test_target() is True
    with pytest.raises(ProductionTargetError):
        env_guard.require_non_production("pytest")


def test_test_marker_alone_cannot_unlock_production(env, monkeypatch):
    env("root", SUPABASE_URL=f"https://{PROD_REF}.supabase.co")
    monkeypatch.setenv(env_guard.TEST_ENV_MARKER, "1")
    with pytest.raises(ProductionTargetError):
        env_guard.require_non_production("pytest")


def test_undeclared_target_is_refused(env):
    """Fails closed: unknown is treated as production."""
    env("root", DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/whatever")
    assert env_guard.production_signals() == []
    assert env_guard.is_test_target() is False
    with pytest.raises(ProductionTargetError) as exc:
        env_guard.require_non_production("pytest")
    assert "no declared target" in str(exc.value)


def test_declared_test_target_is_allowed(env):
    env("test", BLUNTLY_TEST_ENV="1", APP_ENV="test",
        DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/bluntly_test",
        SUPABASE_URL="https://miysywhcdqkoniaibglx.supabase.co")
    env_guard.load_test_env()
    assert env_guard.production_signals() == []
    assert env_guard.is_test_target() is True
    env_guard.require_non_production("pytest")  # must not raise


def test_env_test_on_disk_counts_because_settings_reads_it(env):
    """The inverse of what this test used to assert, and the reason why.

    It previously required that a `.env.test` on disk NOT affect the verdict,
    because pydantic-settings did not read that file - only a launcher that
    exported it into the environment did. That launcher silently failed:
    PowerShell deletes a variable assigned an empty string, so every `KEY=`
    blanking line vanished, pydantic fell back to the production .env, and the
    dev stack announced "test" while connected to production.

    `.env.test` is now a real env_file with the highest precedence, so the
    guard reads it too. Same file, same precedence, one answer.
    """
    env("root", SUPABASE_URL=f"https://{PROD_REF}.supabase.co")
    env("test", BLUNTLY_TEST_ENV="1", SUPABASE_URL="https://safe.supabase.co")
    assert env_guard.is_test_target() is True
    assert env_guard.production_signals() == [], (
        "the test file overrides the production root .env, as Settings does")
    env_guard.require_non_production("pytest")


def test_environment_variable_overrides_the_file(env, monkeypatch):
    """CI sets real env vars; they must win over a checked-out file."""
    env("test", BLUNTLY_TEST_ENV="1", SUPABASE_URL="https://safe.supabase.co")
    monkeypatch.setenv("SUPABASE_URL", f"https://{PROD_REF}.supabase.co")
    assert env_guard.production_signals(), "os.environ must take precedence"


def test_allow_production_is_an_explicit_argument_only(env):
    env("root", SUPABASE_URL=f"https://{PROD_REF}.supabase.co")
    # The escape hatch works when passed deliberately...
    env_guard.require_non_production("seeder", allow_production=True)
    # ...and there is no environment variable that achieves the same thing.
    assert not any("ALLOW" in k.upper() for k in env_guard._KEYS)


def test_describe_target_never_leaks_a_password(env):
    env("root", SUPABASE_CONNECTION_STRING_SESSION_POOLER=
        "postgres://postgres.abc:sup3rs3cret@aws-0.pooler.supabase.com:5432/postgres")
    described = env_guard.describe_target()
    assert "sup3rs3cret" not in described
    assert "postgres.abc" not in described
    assert "aws-0.pooler.supabase.com" in described


def test_guard_cli_refuses_fixture_scripts_even_with_the_flag(env):
    env("root", SUPABASE_URL=f"https://{PROD_REF}.supabase.co")
    with pytest.raises(SystemExit) as exc:
        env_guard.guard_cli("seed", argv=[env_guard.PRODUCTION_OVERRIDE_FLAG],
                            production_is_legitimate=False)
    assert exc.value.code == 1


def test_guard_cli_allows_a_legitimate_production_script_with_the_flag(env):
    env("root", SUPABASE_URL=f"https://{PROD_REF}.supabase.co")
    allowed = env_guard.guard_cli("hide_test_content",
                                  argv=[env_guard.PRODUCTION_OVERRIDE_FLAG],
                                  production_is_legitimate=True)
    assert allowed is True


def test_guard_cli_refuses_a_legitimate_script_without_the_flag(env):
    env("root", SUPABASE_URL=f"https://{PROD_REF}.supabase.co")
    with pytest.raises(SystemExit) as exc:
        env_guard.guard_cli("hide_test_content", argv=[],
                            production_is_legitimate=True)
    assert exc.value.code == 1


def test_env_files_resolve_against_the_working_directory(tmp_path, monkeypatch):
    """The guard must read what Settings reads, and Settings reads cwd-relative.

    Resolving from this module's own location instead meant `backend/.env.test`
    counted for a process started in the repo root, where pydantic never opens
    it. That file blanks the production connection strings, so the guard
    reported `target: test | db host: localhost` for a live production
    connection and cleared destructive work to run against it.
    """
    monkeypatch.chdir(tmp_path)
    assert env_guard._settings_env_files() == (
        str(tmp_path.parent / ".env"), str(tmp_path / ".env"),
        str(tmp_path / ".env.test"))


def test_the_resolved_connection_outranks_the_files(env, monkeypatch):
    """What Settings actually opened beats any reconstruction from env files.

    The files are a guess at the target; an imported config object is the
    target. When the two disagree the connection wins, so no arrangement of
    `.env*` on disk can talk the guard out of a production database.
    """
    env("test", BLUNTLY_TEST_ENV="1", DATABASE_URL="postgresql://localhost/x")
    assert env_guard.production_signals() == []
    env_guard.require_non_production("a genuinely local run")  # must not raise

    monkeypatch.setattr(
        env_guard, "_resolved_connection",
        lambda: f"postgresql://u:p@aws-0.pooler.supabase.com:5432/{PROD_REF}")

    assert env_guard.production_signals(), \
        "a production connection must be detected even when the files say test"
    with pytest.raises(ProductionTargetError):
        env_guard.require_non_production("wipe the database")


def test_describe_target_reports_the_connection_not_the_files(env, monkeypatch):
    """The printed banner is what a human trusts before running something."""
    env("test", BLUNTLY_TEST_ENV="1", DATABASE_URL="postgresql://localhost/x")
    monkeypatch.setattr(
        env_guard, "_resolved_connection",
        lambda: f"postgresql://u:secret@aws-0.pooler.supabase.com:5432/{PROD_REF}")

    described = env_guard.describe_target()
    assert described.startswith("PRODUCTION")
    assert "localhost" not in described
    assert "secret" not in described


def test_the_reported_project_ref_matches_the_reported_host(env):
    """One banner must not name the test project beside the production host.

    The ref came from SUPABASE_URL while the host came from the connection
    string, so a refused alembic run printed the production pooler host next to
    the test project's ref. Anyone reading it to confirm what they were about
    to touch got a contradiction.
    """
    env("root", SUPABASE_CONNECTION_STRING_SESSION_POOLER=
        f"postgres://postgres.{PROD_REF}:pw@aws-0.pooler.supabase.com:5432/postgres")
    env("test", SUPABASE_URL="https://miysywhcdqkoniaibglx.supabase.co")

    described = env_guard.describe_target()
    assert PROD_REF in described
    assert "miysywhcdqkoniaibglx" not in described
