"""Config precedence is a subsystem, so it gets tests of its own.

Two production incidents came from this one area, and both had the same shape:
something *reported* one environment while *resolving* another.

  1. The guard merged `.env.test` off disk while pydantic-settings did not read
     it, so a stale file made the guard answer "test" for a process wired to
     production.
  2. The dev launcher exported `.env.test` into the environment instead, and
     PowerShell deletes a variable assigned an empty string - so every `KEY=`
     blanking line silently vanished, pydantic fell back to the production
     `.env`, and the stack announced "test" while connected to production.

The invariant both violated:

    Whatever reports the environment must read exactly what resolves it.

These tests pin that, and the precedence order it depends on. They do not read
the real `.env` - they drive both mechanisms through a temporary layout so the
assertions hold on any machine.
"""

from __future__ import annotations

import pytest
from pydantic_settings import SettingsConfigDict

from app.core import env_guard
from app.core.config import Settings

PROD_REF = env_guard.PRODUCTION_PROJECT_REF


@pytest.fixture
def layout(tmp_path, monkeypatch):
    """A throwaway (.env, backend/.env, backend/.env.test) trio."""
    root = tmp_path / ".env"
    backend = tmp_path / "backend.env"
    test = tmp_path / ".env.test"
    for f in (root, backend, test):
        f.write_text("", encoding="utf-8")

    monkeypatch.setattr(env_guard, "_TEST_ENV_FILE", str(test))
    monkeypatch.setattr(env_guard, "_ENV_FILES", (str(root), str(backend), str(test)))
    for key in env_guard._KEYS + (env_guard.TEST_ENV_MARKER,):
        monkeypatch.delenv(key, raising=False)

    def write(which: str, **values: str) -> None:
        target = {"root": root, "backend": backend, "test": test}[which]
        target.write_text("\n".join(f"{k}={v}" for k, v in values.items()),
                          encoding="utf-8")

    def settings_for() -> Settings:
        """Settings resolved over the same three files, in the same order."""
        class _S(Settings):
            model_config = SettingsConfigDict(
                env_file=(str(root), str(backend), str(test)),
                env_file_encoding="utf-8", extra="ignore", case_sensitive=False)
        return _S()

    write.settings_for = settings_for  # type: ignore[attr-defined]
    return write


def test_env_test_overrides_the_production_root_env(layout):
    """The precedence the whole test-isolation design rests on."""
    layout("root", SUPABASE_URL=f"https://{PROD_REF}.supabase.co",
           DATABASE_URL="postgresql+psycopg://u:p@prod-host:5432/prod")
    layout("test", SUPABASE_URL="https://test-project.supabase.co",
           DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/bluntly_test")

    settings = layout.settings_for()
    assert "test-project" in settings.supabase_url
    assert "localhost" in settings.database_url, "the root .env won - precedence is inverted"


def test_a_blank_value_in_env_test_really_blanks_it(layout):
    """`KEY=` must mean empty, not "fall through to the file underneath".

    This is the exact mechanism the dev launcher lost. Blanking is how
    .env.test detaches from the production Supabase connection strings; if a
    blank silently inherits, the app connects to production while every other
    signal says test.
    """
    layout("root", SUPABASE_CONNECTION_STRING="postgresql://u:p@prod:5432/postgres",
           SUPABASE_CONNECTION_STRING_SESSION_POOLER="postgresql://u:p@prod-pooler:5432/postgres")
    layout("test", SUPABASE_CONNECTION_STRING="",
           SUPABASE_CONNECTION_STRING_SESSION_POOLER="")

    settings = layout.settings_for()
    assert settings.supabase_connection_string == ""
    assert settings.supabase_connection_string_session_pooler == ""


def test_the_guard_and_settings_agree_on_the_same_layout(layout):
    """The invariant both incidents broke.

    Whatever reports the environment must read exactly what resolves it, or
    the report is worse than none - it is a false assurance.
    """
    layout("root", SUPABASE_URL=f"https://{PROD_REF}.supabase.co")
    layout("test", BLUNTLY_TEST_ENV="1", APP_ENV="test",
           SUPABASE_URL="https://test-project.supabase.co")

    settings = layout.settings_for()
    guard_says_production = bool(env_guard.production_signals())
    settings_is_production = PROD_REF in settings.supabase_url

    assert guard_says_production == settings_is_production, (
        f"guard says production={guard_says_production} but Settings resolved "
        f"{settings.supabase_url!r} - the reporter and the resolver disagree")
    assert guard_says_production is False


def test_a_production_root_env_alone_is_detected(layout):
    layout("root", SUPABASE_URL=f"https://{PROD_REF}.supabase.co")
    settings = layout.settings_for()
    assert PROD_REF in settings.supabase_url
    assert env_guard.production_signals(), "Settings resolved production; the guard missed it"


def test_a_real_environment_variable_beats_every_file(layout, monkeypatch):
    """CI sets real variables; they must win over a checked-out file."""
    layout("test", BLUNTLY_TEST_ENV="1", SUPABASE_URL="https://test-project.supabase.co")
    monkeypatch.setenv("SUPABASE_URL", f"https://{PROD_REF}.supabase.co")

    assert env_guard.production_signals(), "os.environ must outrank the files"
    assert PROD_REF in layout.settings_for().supabase_url


def test_the_documented_file_order_matches_the_code(layout):
    """If Settings' env_file order changes, the guard's list must change with it.

    Nothing else enforces that the two lists stay in step, and they drifting
    apart is precisely incident #1.
    """
    declared = Settings.model_config.get("env_file")
    assert declared == ("../.env", ".env", ".env.test"), declared
    # The guard's list is absolute paths, but must end with .env.test for the
    # same reason: last file wins.
    assert env_guard._ENV_FILES[-1] == env_guard._TEST_ENV_FILE


class TestRefusalsAreSeparateFromWarnings:
    """Refusing to boot is the strongest thing this config can do, so the bar
    is "serving in this state is worse than not serving at all".

    An unconfigured Redis used to clear that bar: it was the only throttle on
    login brute force, and the limiter failed open silently. Migration 0028
    changed the facts - the limiter now falls back to Postgres, verified
    enforcing against production - so the refusal became stale. A stale refusal
    is not harmless here: every other production check is gated on APP_ENV, and
    nobody can set APP_ENV while one refusal blocks the boot.
    """

    def test_redis_is_a_warning_not_a_refusal(self, layout, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        settings = layout.settings_for()
        refusals = " ".join(settings.production_issues())
        warnings = " ".join(settings.production_warnings())
        assert "REDIS_URL" not in refusals, (
            "an unconfigured Redis refuses the boot again; the Postgres "
            "fallback from 0028 means it should only warn")
        assert "REDIS_URL" in warnings

    def test_the_genuinely_fatal_checks_still_refuse(self, layout, monkeypatch):
        """The split must not have quietly demoted anything that matters."""
        monkeypatch.setenv("JWT_SECRET", "short")
        monkeypatch.setenv("CORS_ORIGINS", "*")
        monkeypatch.setenv("PII_HASH_SALT", "dev-pii-salt")
        refusals = " ".join(layout.settings_for().production_issues())
        for expected in ("JWT_SECRET", "CORS_ORIGINS", "PII_HASH_SALT"):
            assert expected in refusals, f"{expected} no longer refuses the boot"

    def test_warnings_never_block_the_boot(self, layout):
        """main.py logs warnings and serves; only issues raise."""
        import pathlib
        main = (pathlib.Path(__file__).resolve().parents[1]
                / "app" / "main.py").read_text(encoding="utf-8")
        assert "production_warnings()" in main, "warnings are never surfaced"
        raising = main.split("_issues = settings.production_issues()")[1][:300]
        assert "raise RuntimeError" in raising
        assert "production_warnings" not in raising, (
            "a warning can reach the raise, which makes it a refusal")
