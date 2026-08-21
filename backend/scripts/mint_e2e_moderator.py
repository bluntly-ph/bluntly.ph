"""Mint a moderator session token for the moderator-only E2E spec.

`e2e/moderator-a11y.spec.ts` needs a moderator, and the generic accessibility
suite deliberately runs without credentials. This creates a throwaway moderator
in the ISOLATED TEST environment and prints its token.

It refuses production outright and has no override, because there is no good
reason to mint a privileged session against the live site: doing so means
either promoting a real user or leaving a moderator fixture behind.

Usage:
    cd backend && python -m scripts.mint_e2e_moderator
    # then, from the repo root:
    E2E_MODERATOR_TOKEN=<printed> npx playwright test e2e/moderator-a11y.spec.ts

    # and afterwards:
    cd backend && python -m scripts.mint_e2e_moderator --cleanup
"""

from __future__ import annotations

import argparse
import uuid

from sqlalchemy import text

from app.core.env_guard import guard_cli
from app.db.session import SessionLocal

MARKER = "E2E Moderator"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cleanup", action="store_true",
                    help="Remove every account this script created.")
    args = ap.parse_args()

    # production_is_legitimate=False: no flag unlocks this against production.
    guard_cli("mint_e2e_moderator", production_is_legitimate=False)

    from fastapi.testclient import TestClient

    from app.main import app

    with SessionLocal() as db:
        if args.cleanup:
            removed = db.execute(
                text("DELETE FROM users WHERE display_name = :m"), {"m": MARKER}).rowcount
            db.commit()
            print(f"removed {removed} E2E moderator account(s)")
            return 0

        client = TestClient(app)
        email = f"e2e_mod_{uuid.uuid4().hex}@example.com"
        resp = client.post("/api/v1/auth/register", json={
            "email": email, "password": "password123", "display_name": MARKER})
        if resp.status_code != 201:
            print(f"register failed: HTTP {resp.status_code} {resp.text[:160]}")
            return 1
        body = resp.json()
        db.execute(text("UPDATE users SET role='moderator' WHERE id = :i"),
                   {"i": body["user"]["id"]})
        db.commit()

    print("\nA throwaway moderator was created in the test environment.\n")
    print("Run the spec with:")
    print(f'  E2E_MODERATOR_TOKEN={body["access_token"]} '
          f'npx playwright test e2e/moderator-a11y.spec.ts')
    print("\nThen clean up:")
    print("  cd backend && python -m scripts.mint_e2e_moderator --cleanup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
