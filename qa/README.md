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

- **`review-photos` Supabase bucket does not exist.** Review photo upload
  (BUG-023) is built and will fail until it is created. See `docs/schema.md`
  for the bucket table.
- **No product has an image.** BUG-009's root cause was that `products.image_url`
  was never exposed by any schema, which is fixed — but 0 of 562 products
  actually have one set. Run `backend/scripts/seed_product_images.py`.

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

## What is still open

- Coverage Checklist rows 41–43 (Q&A), 47 (edit profile), 56–59 (cross-browser),
  60–65 (visual vs Figma), 66–75 (performance, accessibility, data integrity)
  were never started and are untouched here.
