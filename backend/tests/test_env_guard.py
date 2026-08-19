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
    # _ENV_FILES is exactly what Settings reads. .env.test is separate and only
    # counts once load_test_env() has put it into os.environ.
    monkeypatch.setattr(env_guard, "_ENV_FILES", (str(root_env), str(backend_env)))
    monkeypatch.setattr(env_guard, "_TEST_ENV_FILE", str(test_env))
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


def test_an_unloaded_env_test_file_does_not_make_the_guard_say_test(env):
    """The corrected semantics, pinned.

    An earlier version merged .env.test straight off disk, so merely having the
    file made the guard report "test" while pydantic-settings - which does not
    read it - still resolved PRODUCTION from the root .env. The guard has to
    describe the connection the app will actually open.
    """
    env("root", SUPABASE_URL=f"https://{PROD_REF}.supabase.co")
    env("test", BLUNTLY_TEST_ENV="1", SUPABASE_URL="https://safe.supabase.co")
    # Not loaded yet -> still production, and still refused.
    assert env_guard.is_test_target() is False
    assert env_guard.production_signals()
    with pytest.raises(ProductionTargetError):
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
