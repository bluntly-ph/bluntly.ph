"""Refuse to run destructive work against production.

Why this exists: on 2026-08-19 the full pytest suite was run against the
production database, because it is the only database this project has. It
created hundreds of fixture reviews on the live site. The remedy cannot be
"remember not to do that" - it has to be enforced before the first write.

Two design decisions worth keeping:

**Multiple signals, not one env var.** The repo-root `.env` sets
`USE_SUPABASE=true` and does not set `APP_ENV` at all, so `app_env` silently
defaults to "local" while every connection goes to production. A guard that
trusted an environment name would have concluded "this is local" and waved the
suite through. So we look at what the connection actually points at.

**Fails closed.** An unrecognised target is treated as production. Getting this
backwards - assuming unknown means safe - is how a guard quietly stops
guarding.

Nothing here is a secret. A Supabase project ref appears in every public
storage URL the site serves; it is an identifier, not a credential.
"""

from __future__ import annotations

import os
import re

# The production Supabase project. Public: it is in every image URL on the
# live site. Hardcoded on purpose - deriving it from configuration would mean
# the guard reads the same value it is supposed to be checking.
PRODUCTION_PROJECT_REF = "byobedbhodhvocgrkrse"
PRODUCTION_SITE_HOSTS = ("www.bluntly.ph", "bluntly.ph")

# Set by a test environment to declare itself. Presence alone is never enough:
# the connection still has to not look like production.
TEST_ENV_MARKER = "BLUNTLY_TEST_ENV"

# The deliberate, documented override for the rare script that must touch
# production (e.g. the one-off image seeder run by the owner).
PRODUCTION_OVERRIDE_FLAG = "--allow-production"


class ProductionTargetError(RuntimeError):
    """Raised when a destructive operation is aimed at production."""


_KEYS = (
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_CONNECTION_STRING",
    "SUPABASE_CONNECTION_STRING_SESSION_POOLER",
    "SUPABASE_CONNECTION_STRING_TRANSACTION_POOLER",
    "NEXT_PUBLIC_API_URL",
    "NEXT_PUBLIC_SITE_URL",
    "APP_ENV",
)

# The same files pydantic-settings resolves for Settings, in the same order.
# Relative to backend/app/core/ -> backend/ -> repo root.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
_ENV_FILES = (
    os.path.join(_REPO_ROOT, ".env"),
    os.path.join(_BACKEND_DIR, ".env"),
    os.path.join(_BACKEND_DIR, ".env.test"),
)


def _read_env_file(path: str) -> dict[str, str]:
    if not os.path.isfile(path):
        return {}
    found: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                found[key.strip().upper()] = value.strip().strip('"').strip("'")
    except OSError:
        return {}
    return found


def _values() -> dict[str, str]:
    """The strings identifying the target, resolved the way the APP resolves them.

    Reading only `os.environ` was not enough and nearly made this guard
    decorative: the production credentials live in the repo-root `.env` FILE,
    never exported, so a guard that consulted the process environment alone saw
    nothing and concluded "unrecognised". Anyone who then set the test marker
    would have sailed straight into production.

    So we merge the same env files `Settings` reads, with real environment
    variables taking precedence - mirroring pydantic-settings' own order.
    """
    merged: dict[str, str] = {}
    for path in _ENV_FILES:
        merged.update(_read_env_file(path))
    for key in _KEYS:
        from_environ = os.getenv(key)
        if from_environ is not None:
            merged[key.upper()] = from_environ
    return {k: (merged.get(k) or "").lower() for k in _KEYS}


def production_signals(extra: dict[str, str] | None = None) -> list[str]:
    """Every reason to believe the current target is production.

    Returns human-readable reasons rather than a bool so the abort message can
    say *why*, which is the difference between a developer fixing their config
    and a developer disabling the guard.
    """
    values = _values()
    if extra:
        values.update({k: (v or "").lower() for k, v in extra.items()})
    signals: list[str] = []

    if values.get("APP_ENV") == "production":
        signals.append("APP_ENV=production")

    for key, value in values.items():
        if not value or key == "APP_ENV":
            continue
        if PRODUCTION_PROJECT_REF in value:
            signals.append(f"{key} references the production Supabase project")
        if any(host in value for host in PRODUCTION_SITE_HOSTS):
            signals.append(f"{key} points at the production site")

    # De-duplicate while keeping order stable for readable messages.
    seen: set[str] = set()
    return [s for s in signals if not (s in seen or seen.add(s))]


def is_test_target() -> bool:
    """True only when a target has positively declared itself a test target.

    Declaring is necessary but not sufficient - `require_non_production` still
    checks the connection. A stale marker left in a shell must not be able to
    unlock production.
    """
    if os.getenv(TEST_ENV_MARKER):
        return True
    for path in _ENV_FILES:
        if _read_env_file(path).get(TEST_ENV_MARKER):
            return True
    return False


def describe_target() -> str:
    """A safe, printable description of what is about to be written to.

    Shows the database host and Supabase project ref only. Never the user,
    password, or query string - this string is designed to be printed by
    scripts and to end up in terminal scrollback and CI logs.
    """
    values = _values()
    raw = (values.get("SUPABASE_CONNECTION_STRING_SESSION_POOLER")
           or values.get("SUPABASE_CONNECTION_STRING")
           or values.get("DATABASE_URL") or "")
    host = "unknown"
    match = re.search(r"@([^/:?]+)", raw)
    if match:
        host = match.group(1)
    ref = "unknown"
    ref_match = re.search(r"([a-z]{20})\.supabase\.co", values.get("SUPABASE_URL", ""))
    if ref_match:
        ref = ref_match.group(1)
    elif PRODUCTION_PROJECT_REF in raw:
        ref = PRODUCTION_PROJECT_REF
    label = "PRODUCTION" if production_signals() else (
        "test" if is_test_target() else "unrecognised")
    return f"{label} | db host: {host} | supabase project: {ref}"


def require_non_production(action: str, *, allow_production: bool = False) -> None:
    """Abort `action` unless the target is demonstrably not production.

    `allow_production=True` is the deliberate escape hatch for scripts the
    owner genuinely runs against production. It is a parameter rather than an
    environment variable so it cannot be left switched on in a shell profile.
    """
    signals = production_signals()

    if signals:
        if allow_production:
            return
        raise ProductionTargetError(
            f"\n{'=' * 68}\n"
            f"TEST RUN REFUSED - {action} is aimed at PRODUCTION\n"
            f"{'=' * 68}\n"
            f"Target: {describe_target()}\n\n"
            "Detected:\n" + "".join(f"  - {s}\n" for s in signals) +
            "\nNothing has been written.\n\n"
            "Point this at the test environment instead:\n"
            "  1. copy backend/.env.test.example to backend/.env.test\n"
            "  2. fill in the test Supabase project's values\n"
            "  3. re-run\n\n"
            "See docs/ENVIRONMENTS.md. If you genuinely need to run against\n"
            "production, the script must be invoked with an explicit\n"
            f"{PRODUCTION_OVERRIDE_FLAG} flag - there is no environment\n"
            "variable that unlocks this.\n"
            f"{'=' * 68}\n"
        )

    if not is_test_target():
        if allow_production:
            return
        raise ProductionTargetError(
            f"\n{'=' * 68}\n"
            f"TEST RUN REFUSED - {action} has no declared target\n"
            f"{'=' * 68}\n"
            f"Target: {describe_target()}\n\n"
            "The target did not identify itself as a test environment, and an\n"
            "unrecognised target is treated as production. This is deliberate:\n"
            "a guard that assumes 'unknown means safe' does not guard anything.\n\n"
            f"Set {TEST_ENV_MARKER}=1 in backend/.env.test alongside that\n"
            "environment's credentials. See docs/ENVIRONMENTS.md.\n"
            f"{'=' * 68}\n"
        )


def guard_cli(action: str, *, argv: list[str] | None = None,
              production_is_legitimate: bool = False) -> bool:
    """Entry-point guard for a script that writes.

    Prints the target before doing anything - a script that wipes tables should
    say out loud what it is about to wipe them in - then enforces the rule.

    `production_is_legitimate=True` marks the handful of scripts that exist to
    be run against production by the owner (the image seeder, the test-content
    sweep, the receipt migration). Those still refuse by default; they just
    accept `--allow-production` as an answer. Everything else has no answer at
    all, because there is no good reason to seed fixtures into the live site.

    Returns True when the caller may proceed against production.
    """
    import sys

    args = sys.argv[1:] if argv is None else argv
    allow = PRODUCTION_OVERRIDE_FLAG in args

    print(f"[env] {action} -> {describe_target()}")

    if allow and not production_is_legitimate:
        # Same clean exit as every other refusal in this function. Two refusal
        # paths that behave differently is how a caller ends up handling one
        # and not the other.
        print(
            f"\n{action} does not accept {PRODUCTION_OVERRIDE_FLAG}.\n"
            "This script creates or destroys fixture data. There is no\n"
            "legitimate reason to run it against production, so the override\n"
            "is not wired up here on purpose.\n",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        require_non_production(action,
                               allow_production=allow and production_is_legitimate)
    except ProductionTargetError as exc:
        # A clean message and a non-zero exit, not a traceback. The person who
        # needs to read this is usually not the person who wrote the script.
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    return allow
