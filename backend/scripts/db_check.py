"""Check the effective database connection (local or Supabase).

Prints the resolved target (password masked) and attempts a real connection with
the same SSL/pooler settings the app uses. Useful before running migrations.

Run against Supabase:  USE_SUPABASE=true python -m scripts.db_check
"""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import settings

#: This tool exists to answer "can I reach the database". Borrowing the
#: application engine means borrowing its lack of a connect timeout, and a
#: diagnostic that hangs has not diagnosed anything.
CONNECT_TIMEOUT_SECONDS = 5


def main() -> int:
    url = make_url(settings.effective_database_url)
    print(f"target: {url.render_as_string(hide_password=True)}")
    print(f"use_supabase={settings.use_supabase}  connect_args={settings.db_connect_args}")
    engine = create_engine(
        settings.effective_database_url,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
        pool_pre_ping=False,
    )
    try:
        with engine.connect() as conn:
            version = conn.execute(text("select version()")).scalar()
            n_tables = conn.execute(text(
                "select count(*) from information_schema.tables "
                "where table_schema='public' and table_type='BASE TABLE'"
            )).scalar()
        print(f"CONNECTED [ok]  {str(version)[:50]}")
        print(f"public tables: {n_tables}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"CONNECT FAILED [x]  {type(exc).__name__}: {str(exc)[:220]}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
