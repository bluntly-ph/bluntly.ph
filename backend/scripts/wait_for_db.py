"""Block until the database accepts connections, then exit 0.

Used by the api container's startup command so a transient "DB/DNS not ready yet"
race at `docker compose up` retries instead of crashing the container.
"""

from __future__ import annotations

import sys
import time

from sqlalchemy import create_engine, text

from app.core.config import settings

ATTEMPTS = 30
DELAY_SECONDS = 2


def main() -> int:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"database ready (attempt {attempt})")
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"waiting for database ({attempt}/{ATTEMPTS}): {exc}")
            time.sleep(DELAY_SECONDS)
    print("database never became ready", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
