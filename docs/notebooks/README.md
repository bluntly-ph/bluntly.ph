# Notebooks

## `bluntly-algorithms.ipynb`

Capstone defense material: every algorithm in the backend, documented and simulated.
90 cells (48 code / 42 markdown), 22 charts, 21 algorithms cited by `file:line` derived
from `inspect.getsourcelines` rather than hand-typed.

Nothing in it is retyped from the source. The setup cell puts `backend/` on `sys.path` and
imports the live modules, so a formula that changes in `app/services/` changes here too.

### Running it locally

```
cd backend && .venv/Scripts/python.exe -m jupyter lab ../docs/notebooks/bluntly-algorithms.ipynb
```

Needs no database and no `.env` — every setting it touches has a default, and the
notebook imports only pure functions. It does need the repository on disk, because that
is what it is documenting.

### Running it on Google Colab

The saved `.ipynb` carries all 22 charts and every text output inline, so **uploading it
to Colab renders the whole thing immediately** — nothing needs to run for it to be
readable or presentable. Re-execution is the only thing that needs setup.

To re-execute: `File → Upload notebook`, then put this cell **above** the existing setup
cell and run it first.

```python
# --- Colab bootstrap: fetch the code the notebook documents -------------------
!git clone --depth 1 https://github.com/bluntly-ph/bluntly.ph.git
%cd bluntly.ph
!pip install -q ./backend
```

Three details, each of which breaks the run if skipped:

1. **`%cd bluntly.ph` is required.** The setup cell finds the repository by walking *up*
   from `Path.cwd()` looking for `backend/app/services/ranking.py`. Colab starts in
   `/content`; the clone lands in `/content/bluntly.ph`, which is *down*, not up. Without
   the `%cd` the cell raises `RuntimeError: repository root not found`.
2. **`pip install ./backend` uses the real manifest** (`backend/pyproject.toml`), so the
   dependency set cannot drift from what the backend actually declares. It pulls more than
   the notebook strictly needs — psycopg, celery, redis, supabase — and takes a minute or
   two. That is the price of not maintaining a second, forkable list.
3. **Restart the runtime if Colab asks.** `pip install` may upgrade a package Colab
   preloaded; the imports are only safe after the restart.

Colab already ships matplotlib, so the plotting cell needs nothing.

The repository is public, so the clone needs no token. If it is ever made private, swap the
clone for a `files.upload()` of a zipped `backend/` — the rest is unchanged.
