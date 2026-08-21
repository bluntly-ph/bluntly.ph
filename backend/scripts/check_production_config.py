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
import os


def _load_env_file(path: str) -> int:
    """Put a `vercel env pull` file into os.environ. Returns how many keys.

    Real environment variables win, matching pydantic-settings, so an export in
    the shell still overrides the file.

    This has to happen before `app.core.config` is imported: pydantic reads its
    `env_file` once, at import, and resolves it against the CURRENT WORKING
    DIRECTORY. A pulled `.env.production` is not one of the names it looks for
    under any cwd, so without this the script would cheerfully report on the
    developer's local configuration while claiming to describe production —
    the same class of mistake that let the production guard call a live
    database "test".
    """
    loaded = 0
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            # `vercel env pull` quotes values; strip one matched pair.
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if os.environ.setdefault(key.strip(), value) == value:
                loaded += 1
    return loaded


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true",
                    help="Exit non-zero when the app would refuse to boot.")
    ap.add_argument("--env-file", metavar="PATH",
                    help="Read production values from this file first, e.g. the "
                         "output of `vercel env pull`. Values are never printed.")
    args = ap.parse_args()

    if args.env_file:
        try:
            count = _load_env_file(args.env_file)
        except OSError as exc:
            print(f"could not read {args.env_file}: {exc}")
            return 2
        print(f"loaded {count} value(s) from {args.env_file} (values not shown)\n")

    try:
        from app.core.config import settings
    except Exception as exc:  # noqa: BLE001
        print(f"could not load settings: {type(exc).__name__}: {exc}")
        return 2

    print(f"APP_ENV currently        : {settings.app_env!r}")
    print(f"is_production            : {settings.is_production}")
    print(f"production checks running: {settings.is_production}\n")

    issues = settings.production_issues()
    warnings = settings.production_warnings()

    if warnings:
        print(f"{len(warnings)} warning(s) - these do NOT stop the app serving:")
        print()
        for warning in warnings:
            print(f"  ~ {warning}")
        print()

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
