# QA bug tracker — how to apply these

These files update the **Bug Log** tab of the
[bluntly.ph QA Bug Tracker](https://docs.google.com/spreadsheets/d/1CP3qiD1YSTTtKTPWl28dr8AYXcnrV33svCx7s5T2y1s/edit?gid=38658182).

They are deliberately **not** a full replacement for the sheet. QA wrote columns
A–S (the summary, steps, expected/actual, evidence) and that prose is the record
of what was actually observed — overwriting it with a regenerated version would
lose wording and risk mangling multi-line cells. So these files touch only what
the fix work actually changed.

## 1. `bug-log-status.tsv` — status for BUG-001 … BUG-026

Five columns, matching **Status, Assigned To, Date Fixed, Retest Result, Notes**
(the last five columns of the Bug Log, `T`–`X` if nothing has been inserted).
26 rows in Bug ID order, plus a header row.

1. Open the **Bug Log** tab.
2. Click the **Status** cell on the **BUG-001** row.
3. Paste the file's contents *without* its header row.
4. Check the alignment before saving: the last pasted row must land on BUG-026.

If a row has been inserted or reordered since this was generated, the rows will
be off by one — verify against a couple of Bug IDs rather than trusting the
paste. Status values are the ones already in the **Lists** tab, so the existing
dropdowns keep working.

## 2. `bug-log-new-rows.tsv` — two new rows

Full 24-column rows for **BUG-027** and **BUG-028**, the two responsive issues
that Coverage Checklist rows 53 and 55 recorded as `BUG-XXX` and that never got
Bug Log entries. Paste at the first empty row below BUG-026.

Once pasted, update Coverage Checklist rows 53 and 55 to reference BUG-027 and
BUG-028 instead of `BUG-XXX`.

## Two things need doing outside the code

Both are flagged in the Notes column too, but they are the kind of thing that
gets lost in a spreadsheet:

~~Both done on 2026-08-19.~~ Kept here because the diagnosis is the useful part:

- **The storage buckets did not exist.** Only `avatars` did. Review photo
  upload (BUG-023) and every product image failed at the storage layer —
  below anything the application could see or report, which is why both looked
  like content problems. `product-images` and `review-photos` are now created
  (public read, 5 MB / 8 MB, png/jpeg/webp), and both upload paths are verified
  end to end. See `docs/schema.md`.
- **Products now have images.** No product has a genuine `source_url` to read
  an `og:image` from, so the seeder gained `--from-file`, taking a checked-in
  `canonical_name`→page-URL map instead of inventing `source_url` values.
  5 of the 6 products on the feed resolved and were checked by eye, not on
  status code — that is how a wrong-generation MacBook image got caught before
  it shipped. Uniqlo serves a bot challenge and keeps the placeholder.

## BUG-029 — receipts were in a public bucket (P0, 2026-08-19)

Filed as a new ID rather than folded into BUG-023, because it is a different
defect: BUG-023 was "upload does not work", this is "upload worked and put a
customer's receipt somewhere anyone could read it". The full row is in
`bug-log-new-rows.tsv`; paste it below BUG-028.

The short version: `POST /reviews/photo` was documented as returning "a URL
suitable for `photo_url` / `receipt_url`", so one function served two
audiences and the caller's convention — not the server — decided whether an
object was public. A receipt therefore landed in the public `review-photos`
bucket behind a permanent URL, and `receipt_url` rode on `ReviewOut`, which
anonymous callers receive for any published review.

Two things make it worth reading rather than just retesting:

- **Tracing found a second, independent leak.** `review_versions.snapshot`
  embedded `receipt_url` in all 675 rows, and both version endpoints serve
  anonymous callers. Fixing only the field on `ReviewOut` would have left it.
- **An unguessable UUID is not authorization.** It cannot be revoked, never
  expires, and leaks through history, `Referer` headers, proxy logs and
  screenshots — and the API itself was about to hand it out on publish.

**How to retest** (no production receipt needed):

1. Sign in, start a review, attach a proof of purchase. The response must
   contain a `key`, not a public URL, and the preview must not survive a page
   reload — a signed preview URL is deliberately never persisted.
2. Publish that review as a moderator. `GET /api/v1/reviews/{id}` and
   `GET /api/v1/reviews/{id}/versions` with no credentials must contain no
   `receipt_url`, no `receipt_key`, and no `review-receipts` string.
   `has_receipt: true` is expected and is fine.
3. `GET /api/v1/reviews/{id}/receipt` — anonymous 401, unrelated user 404,
   author and moderator 200 with a signed URL that expires in 300 s.
4. Strip the `?token=` from that signed URL and request it: must be refused.
5. Confirm public review photos still render on the published review.

Automated as `backend/tests/test_receipt_privacy.py` (13 tests), including a
structural guard that fails if any locator field is ever added back to a shared
review schema.

## Receipt-view audit logging: an owner decision, not a defect

Moderator receipt access currently writes no `moderation_logs` entry. Before
treating that as a gap, the requirements were searched. What they actually say:

- **PRD FR-9** requires a "filterable audit log" of platform administration,
  and lists reviewing audit logs among the moderator's duties.
- **`02-bluntly-ph-architecture.md`** maps "Audit log of moderation/admin
  **actions**" to ISO/IEC 27002 8.15.
- `moderation_logs` doubles as the audit log (`DEVIATIONS.md` §4) and already
  carries non-decision admin actions: `csv_import`, `payout`,
  `honesty_fund_distribution`.

Every action logged today changes state. Viewing evidence is a read, and no
document requires logging reads. So this is **not** a contractual requirement
and has deliberately not been implemented — adding it would mean a new
`ModerationAction` enum value, which on Postgres is a schema migration, and
that is scope the owner should agree to rather than inherit.

It is worth doing. The architecture doc's own ISO/IEC 27002 8.15 citation
covers access logging, receipts contain personal data under RA 10173, and
"who looked at this customer's receipt, and when" is exactly the question an
audit log exists to answer. If approved, it should record moderator id, review
id, action, and timestamp — and never the object key, the signed URL, or
anything from the receipt itself.

## BUG-025 was resolved by removing the feature

Tokens were retired in favour of the PHP revenue share, and the request board
was the last thing still spending them — which is what made "you can't see your
balance before you spend it" possible in the first place. Migration **0022**
drops `review_requests.bounty`. Posting is free, up-votes rank the board by
demand rather than raising a purse, and fulfilling a request pays nothing
directly; the reviewer earns from the review itself like any other.

So retest BUG-025 differently: post a request from an account with **zero
tokens** (must succeed), confirm no bounty or token field exists on
`/requests/new`, and confirm the board reads "N waiting" rather than a reward.

The token **ledger is untouched**. `token_transactions` is append-only and every
historical escrow, refund and reward is still there and still readable.

## Deployed, and a data incident you should know about

All of this is live on production as of 2026-08-12 (`ed1baa0`). Verified after
deploy: 16 public routes 200, unknown paths 404, all 8 gated routes 307 to
`/login?next=<path>`, and the request board reading correctly from the new API.

Two things happened on the way there that are worth recording:

**Test data was briefly public again.** This repo has one database and it is
production — `backend/scripts/hide_test_content.py` says so in its own
docstring. Running the backend test suite therefore writes real rows. It was run
several times during this work, and for a period **38 test reviews were visible
on the live site** alongside the 6 genuine ones, which is BUG-010 all over
again. They are hidden now and the public feed is back to exactly the 6 real
reviews. Anyone running `pytest` against this project needs to run
`python -m scripts.hide_test_content --apply` afterwards.

**The request board is genuinely empty now, not broken.** All 51 open requests
were test fixtures and not one belonged to a real account, so the sweep took
them all. `/requests` correctly shows its empty state. The script now covers
requests as well as reviews, and is reversible either way.

**Deploys had been failing silently.** `vercel.json` carried a `"//"` comment
key, which fails Vercel's schema validation outright, so the git integration
produced no build and the site simply stayed on the previous version. The
rationale moved to `docs/DEPLOYMENT.md`; do not put comments back in that file.

## The trust badge now shows a score

Per the product decision, the badge is the level name **and** the number:
**"Verified Buyer · 63"**. Both halves earn their place — all three real
reviewers are "Verified Buyer" but they score 63, 63 and 17, so the level says
what someone has unlocked and the number says how well they are actually doing.

It renders through one `TrustBadge` component (`components/ui/TrustBadge.tsx`,
formatting in `lib/trust.ts`) on all five surfaces that show trust: the featured
card, a review, a public profile, your own profile, and a Q&A answer. Screen
readers hear "Verified Buyer, trust score 63 out of 100".

One retest caveat: the badge is fed by a 60-second Data Cache, so straight after
a deploy it can briefly show the level with no number. That is expected and
clears itself.

## What is still open

- Coverage Checklist rows 41–43 (Q&A), 47 (edit profile), 56–59 (cross-browser),
  60–65 (visual vs Figma), 66–75 (performance, accessibility, data integrity)
  were never started and are untouched here.
