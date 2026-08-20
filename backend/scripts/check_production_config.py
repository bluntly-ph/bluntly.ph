"""Answer "would APP_ENV=production boot?" without changing anything.

`main.py` refuses to start when `production_issues()` returns anything - but it
only consults that list when `APP_ENV` is exactly "production". Whatever the
deployed value is, the app is running, so those checks are not running either:
not the CORS check, not the PII salt, not the postback secret, and not the
Redis one that would have caught auth rate limiting being silently absent.

Setting `APP_ENV=production` to find out is the wrong experiment. If anything
is unset the app refuses to boot, and finding that out in production is an
outage. This asks the same question with the flag left alone.

Run it wherever the production values live - a Vercel shell, or locally with
the production environment exported. It prints **descriptions only, never
values**, so its output is safe to paste into a ticket or a chat.

    python -m scripts.check_production_config          # against current env
    python -m scripts.check_production_config --strict # exit 1 if not ready

Exit codes: 0 ready, 1 not ready (with --strict), 2 could not evaluate.
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true",
                    help="Exit non-zero when the app would refuse to boot.")
    args = ap.parse_args()

    try:
        from app.core.config import settings
    except Exception as exc:  # noqa: BLE001
        print(f"could not load settings: {type(exc).__name__}: {exc}")
        return 2

    print(f"APP_ENV currently        : {settings.app_env!r}")
    print(f"is_production            : {settings.is_production}")
    print(f"production checks running: {settings.is_production}\n")

    issues = settings.production_issues()

    if not issues:
        print("READY - production_issues() is empty.")
        print("Setting APP_ENV=production would boot and would turn on every")
        print("check above. Deploy, then confirm the app is serving.")
        return 0

    print(f"NOT READY - {len(issues)} issue(s). With APP_ENV=production the app")
    print("would raise at import and the deployment would fail to serve:\n")
    for issue in issues:
        print(f"  - {issue}")

    print("\nFix these where the production values are configured (Vercel ->")
    print("Settings -> Environment Variables), re-run this, and only set")
    print("APP_ENV=production once it prints READY.")
    print("\nNames of the variables involved are in .env.example. This script")
    print("never prints a value, so its output is safe to share.")
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
