# Test the bluntly.ph backend on your own computer — M1 to M3

**Who this is for:** anyone who wants to confirm the backend works, without being a
programmer. You will copy and paste a handful of commands. You do **not** need to
install Python, set up a database, or have any passwords or API keys.

**What you will prove:** that all three delivery milestones actually work —
**M1** (accounts, login, reviews, version history, AI critique), **M2** (trust scores,
voting, affiliate links, revenue split, token economy), and **M3** (request board,
contracts, payouts, affiliate report ingestion). One command checks **48 separate
claims** and prints PASS or FAIL for each.

> **Note (2026-07-28):** this was 49 claims until the seller trust-ratings feature
> was withdrawn by owner decision and its verification check removed (`b0f8ba0`).
> The script has been verified by inspection only — **48/48 is expected, not yet
> observed** against a live run. Remove this note once someone runs it for real.

Everything runs on your own machine, on a throwaway database. It touches nothing live,
sends no email, and spends no money.

- **Tester:** ______________  **Date:** __________  **Result:** ☐ PASS  ☐ FAIL

---

## Step 1 — Install Docker Desktop (one time, ~5 minutes)

Docker runs the backend and its database for you, so you don't have to install them.

1. Download **Docker Desktop**: <https://www.docker.com/products/docker-desktop/>
2. Install it, then **open it** and wait until it says **"Engine running"**.

> Leave Docker Desktop open the whole time. If it isn't running, every command below
> will say it cannot connect.

**Also get the code** — either download the repository as a ZIP from GitHub and unzip
it, or if you have Git:

```
git clone https://github.com/bluntly-ph/bluntly.ph.git
```

---

## Step 2 — Open a terminal in the project folder

- **Windows:** open the project folder in File Explorer, then type `powershell` in the
  address bar and press Enter.
- **Mac:** right-click the project folder → **Services** → **New Terminal at Folder**.

You should be in the folder that contains `backend`, `docs`, and `package.json`.

---

## Step 3 — Create the settings file (copy-paste one line)

The backend reads a file named `.env`. For local testing it only needs three harmless
lines — **no real secrets**.

**Windows (PowerShell):**
```
Set-Content -Path .env -Value "APP_ENV=local","JWT_SECRET=local-testing-only-not-a-real-secret","EMAIL_PROVIDER=console"
```

**Mac / Linux:**
```
printf 'APP_ENV=local\nJWT_SECRET=local-testing-only-not-a-real-secret\nEMAIL_PROVIDER=console\n' > .env
```

`EMAIL_PROVIDER=console` means verification codes are printed to the screen instead of
being emailed — nothing leaves your computer.

> Already have a `.env` in this folder? Skip this step; yours will be used.

---

## Step 4 — Start the backend (one command)

```
cd backend
docker compose up -d --build
```

The **first** run downloads and builds things — expect **3–10 minutes** and a lot of
scrolling text. That is normal. Later runs take seconds.

This starts the API, a PostgreSQL database, Redis, and two background workers, and
automatically creates all the database tables.

---

## Step 5 — Confirm it is alive

Open this in your browser: **<http://localhost:8000/health>**

You should see something like:

```json
{"status":"ok","product_id":"bluntly-ph","version":"0.1.0","timestamp":"..."}
```

You can also browse the whole API interactively at **<http://localhost:8000/docs>**.

> Seeing nothing yet? The API waits for the database on first boot. Give it ~30 seconds
> and refresh.

---

## Step 6 — Run the M1–M3 acceptance check ⭐ (the important one)

```
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm verify
```

This registers users, submits and publishes reviews, votes, attaches affiliate links,
imports real commission reports, runs the request board, contracts and payouts — then
checks the results in the database.

**What success looks like** — a long list of `[PASS]` lines grouped by milestone,
ending with:

```
=== MILESTONE CLAIMS: 48/48 verified ===
```

**48/48 means every M1, M2 and M3 claim passed.** (Expected, not yet observed — see
the note in Step 6's introduction.) If any line says `[FAIL]`, copy the
whole output and send it to the team — that is exactly what they need.

---

## Step 7 — Optional: a second, HTTP-level test

The check above drives the app directly. This one goes over the network like a real
client would:

```
docker compose exec api python -m scripts.api_smoke --base-url http://localhost:8000
```

Expect a list of `[PASS]` lines and a summary at the end.

---

## Step 8 — Optional: try it yourself by hand

Open **<http://localhost:8000/docs>** and use the **"Try it out"** buttons.

A good five-minute tour:
1. `POST /api/v1/auth/register` — create an account. Copy the `access_token` from the
   response.
2. Click the green **Authorize** button (top right) and paste the token.
3. `GET /api/v1/auth/me` — you should see your own account.
4. `POST /api/v1/products` then `POST /api/v1/reviews` — submit a review.
5. `GET /api/v1/reviews/{id}` — see the structured review you just wrote.

> **Expected, not a bug:** a new review shows `published_at: null` and
> `earn_eligible_status: "pending"`. Reviews are **not public until a moderator
> publishes them** — that gate is the whole point of the platform.

For the full click-by-click checklists, see `M1_TEST_PLAN.md`, `M2_TEST_PLAN.md`, and
`M3_TEST_PLAN.md`.

---

## Step 9 — When you're done

```
docker compose down
```

To also delete the throwaway test database:

```
docker compose down -v
```

---

## If something goes wrong

| What you see | What it means | Fix |
|---|---|---|
| `docker: command not found` | Docker isn't installed | Redo Step 1 |
| `Cannot connect to the Docker daemon` / `pipe/dockerDesktopLinuxEngine` | Docker Desktop isn't running | Open Docker Desktop, wait for "Engine running" |
| `env file ... .env not found` | Step 3 was skipped, or you're in the wrong folder | Run Step 3 from the folder **above** `backend` |
| `port is already allocated` (5432 or 8000) | Another database or app is using that port | Close it, or stop other Docker projects (`docker compose down`) |
| `/health` won't load | Still starting up | Wait 30s, refresh; then `docker compose logs api` |
| Postgres `unhealthy` | Slow first start | `docker compose down` then Step 4 again |
| Everything is very slow | First-time image download/build | Let it finish; it's fast afterwards |

To see what the backend is doing at any time:

```
docker compose logs api --tail 50
```

---

## What this does and does not prove

**Proves:** the backend's M1–M3 features work end-to-end against a real PostgreSQL
database — including the money paths (revenue split, token ledger, payouts) and the
rules that protect them (no self-voting, one vote per person, reviews needing
moderator approval, affiliate URLs never exposed publicly).

**Does not cover:**
- **The live production database.** That is verified separately with
  `scripts/supabase_verify.py` (schema + whole-database financial invariants) — it is
  aimed at the hosted Supabase database, not this local one, so it is not part of this
  guide.
- **Real emails.** Local runs print codes to the screen on purpose. Live email delivery
  is a production setting.
- **Real PayPal transfers.** Payout scheduling is fully tested through the built-in
  manual rail; connecting live PayPal needs the owner's credentials.
- **The website's look and feel.** That's the frontend — see `FRONTEND_MILESTONES.md`.
