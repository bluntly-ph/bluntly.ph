"""One command that takes the isolated test project from nothing to a verdict.

Everything downstream of the Supabase credential is automated, so the moment
`backend/.env.test` carries a working connection string this runs the whole
blocked branch without anyone having to remember the order:

    validate target -> refuse production -> migrate to head -> verify revision
    -> pytest -> milestone verification -> report

Usage:
    cd backend && python -m scripts.bootstrap_test_env
    cd backend && python -m scripts.bootstrap_test_env --skip-milestones

It exits non-zero if any stage fails, so it is usable as a gate.

Why a script rather than a runbook: the ordering is the part people get wrong,
and this project has already had two production incidents caused by running the
right command against the wrong target. The environment check is not advisory
here - it is the first thing that happens, and nothing else runs if it fails.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

from app.core.env_guard import (
    PRODUCTION_PROJECT_REF,
    TEST_ENV_MARKER,
    describe_target,
    is_test_target,
    production_signals,
)

PYTHON = sys.executable


def _run(label: str, args: list[str], *, stream: bool = False) -> tuple[bool, str]:
    """Run a stage. `stream` echoes each line as it arrives.

    Capturing output and printing it afterwards keeps a passing log tidy, but
    a stage killed by the workflow wall clock then reports NOTHING: the pipe
    dies with the process. Two consecutive 150-minute timeouts on the
    isolated-database job produced zero pytest lines for exactly this reason —
    no test name, no percentage, no way to tell a uniformly slow suite from a
    single hung test.

    The long stage therefore streams. It is noisier, and that is the point: a
    run that gets killed still leaves a trail showing how far it reached.
    """
    print(f"\n=== {label} ===", flush=True)
    started = time.time()
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    if stream:
        collected: list[str] = []
        streamed = subprocess.Popen(
            [PYTHON, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1, env=env)
        assert streamed.stdout is not None
        for raw in streamed.stdout:
            line = raw.rstrip()
            collected.append(line)
            print(f"  {line}", flush=True)
        streamed.wait()
        print(f"  -> exit {streamed.returncode} in {time.time() - started:.1f}s",
              flush=True)
        return streamed.returncode == 0, "\n".join(collected)

    proc = subprocess.run([PYTHON, *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    out = (proc.stdout or "") + (proc.stderr or "")
    lines = [ln for ln in out.splitlines() if ln.strip()]

    if proc.returncode == 0:
        for line in lines[-6:]:
            print(f"  {line}")
    else:
        # Six lines is enough to read a success and nowhere near enough to
        # diagnose a failure. A 33-minute CI run that reports "6 failed,
        # 4 errors" and then hides which six is a run you have to do again.
        #
        # pytest's own "short test summary info" block is exactly the right
        # amount: one line per failure with the reason. Fall back to a longer
        # tail for anything that has no such section (alembic, the verifier).
        marker = next((i for i, ln in enumerate(lines)
                       if "short test summary info" in ln), None)
        if marker is not None:
            print("  --- failures ---")
            for line in lines[marker:][:60]:
                print(f"  {line}")
        else:
            for line in lines[-40:]:
                print(f"  {line}")
    print(f"  -> exit {proc.returncode} in {time.time() - started:.1f}s")
    return proc.returncode == 0, out


def preflight() -> bool:
    """Refuse anything that is not a declared, non-production test target."""
    print("=== target ===")
    print(f"  {describe_target()}")

    signals = production_signals()
    if signals:
        print("\n  REFUSED: this is production.")
        for s in signals:
            print(f"    - {s}")
        print("\n  Nothing was run. Point backend/.env.test at the test project.")
        return False

    if not is_test_target():
        print(f"\n  REFUSED: no {TEST_ENV_MARKER} marker, so the target is not a")
        print("  declared test environment. An unrecognised target is treated as")
        print("  production on purpose.")
        return False

    # Positive confirmation, not just the absence of production signals.
    from sqlalchemy.engine.url import make_url
    from sqlalchemy.exc import ArgumentError

    from app.core.config import settings
    try:
        url = make_url(settings.effective_database_url)
    except ArgumentError:
        # Almost always the same mistake: the *database password* was supplied
        # where a full connection URI belongs. Supabase shows the two a click
        # apart, and the raw SQLAlchemy failure for it is
        # "Could not parse SQLAlchemy URL from given URL string", which does
        # not point at the actual problem.
        #
        # Never print the value - it is a credential either way.
        print("\n  NOT READY: the connection string could not be parsed as a URL.")
        print("\n  This is usually a database *password* supplied where a full")
        print("  connection URI is expected. The value must look like:")
        print("\n    postgresql://postgres.<project-ref>:<password>"
              "@aws-N-<region>.pooler.supabase.com:5432/postgres")
        print("\n  In Supabase: the Connect button (top bar) -> Session pooler,")
        print("  then substitute the password from Settings -> Database.")
        print("  Set it in SUPABASE_CONNECTION_STRING_SESSION_POOLER (locally)")
        print("  or the TEST_SUPABASE_SESSION_POOLER secret (CI).")
        return False
    if PRODUCTION_PROJECT_REF in str(url):
        print("\n  REFUSED: the migration URL references the production project.")
        return False
    if not url.host or url.host == "localhost":
        print("\n  NOT READY: the connection string still points at localhost.")
        print("  The Supabase credential has not been supplied yet - see")
        print("  docs/ENVIRONMENTS.md. This is the one step that needs the owner.")
        return False

    # Supabase offers three connection strings a click apart, and only one of
    # them works from CI. `db.<ref>.supabase.co` is the DIRECT connection: it
    # resolves to IPv6 only, GitHub's runners are IPv4 only, and the result is
    # `Network is unreachable` against a raw IPv6 address - which reads like an
    # outage rather than the wrong string being pasted.
    if (url.host or "").startswith("db.") and url.host.endswith(".supabase.co"):
        print("\n  NOT READY: this is the DIRECT connection string.")
        print(f"  Host {url.host} resolves to IPv6 only, and CI runners are")
        print("  IPv4 only, so the connection cannot be made from here.")
        print("\n  Use the SESSION POOLER string instead. The two differ in both")
        print("  the user and the host:")
        print("\n    direct   postgresql://postgres:<pw>@db.<ref>.supabase.co:5432/postgres")
        print("    pooler   postgresql://postgres.<ref>:<pw>"
              "@aws-N-<region>.pooler.supabase.com:5432/postgres")
        print("\n  In Supabase: Connect -> Session pooler (not Direct connection).")
        return False

    print(f"  migrations -> {url.host}:{url.port}/{url.database}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-milestones", action="store_true",
                    help="Stop after pytest.")
    args = ap.parse_args()

    if not preflight():
        return 2

    stages: list[tuple[str, bool]] = []

    ok, _ = _run("migrate to head", ["-m", "alembic", "-x", "test=1", "upgrade", "head"])
    stages.append(("migrate", ok))
    if not ok:
        print("\nStopping: the schema is not at head, so later results would be noise.")
        return 1

    ok, out = _run("verify schema revision", ["-m", "alembic", "-x", "test=1", "current"])
    at_head = "head" in out.lower()
    stages.append(("revision at head", ok and at_head))

    # -v with the classic style prints one line per test AS IT COMPLETES, which
    # is what makes a killed run diagnosable; --durations names the worst
    # offenders when the run does finish.
    ok, out = _run(
        "pytest",
        ["-m", "pytest", "-v", "-o", "console_output_style=classic",
         "--durations=40", "-p", "no:randomly"],
        stream=True,
    )
    summary = next((ln for ln in out.splitlines()[::-1]
                    if "passed" in ln or "failed" in ln), "no summary")
    stages.append((f"pytest ({summary.strip()})", ok))

    if not args.skip_milestones:
        ok, out = _run("milestone verification", ["-m", "scripts.verify_milestones"])
        claims = next((ln for ln in out.splitlines()[::-1]
                       if "MILESTONE CLAIMS" in ln), "no summary")
        stages.append((f"milestones ({claims.strip()})", ok))

    print("\n=== summary ===")
    for name, passed in stages:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")

    failed = [n for n, p in stages if not p]
    if failed:
        print(f"\n{len(failed)} stage(s) failed.")
        return 1
    print("\nTest environment is fully verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
