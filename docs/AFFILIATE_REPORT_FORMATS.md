# Affiliate report formats — as actually exported (Shopee PH, Lazada PH)

> Derived from real owner-supplied exports (2026-07-15): a Shopee *Affiliate
> Commission Report* (108 rows) and a Lazada *Conversion Report* (218 rows).
> This supersedes the invented CSV contract pinned in the M2 slice-6 plan
> (`click_ref,order_ref,gross_amount,currency,order_status,platform`), which no
> real export matches. **Manual CSV is the permanent ingestion path** (owner
> decision, 2026-07-15; a first-party partnership may replace it later) — so the
> importer must accept these files as they come out of the platform.

## The blocker: attribution needs a sub-ID in the affiliate link

Reconciliation matches a `sessions` row to a report row. The only field that can
carry OUR identifier through the marketplace and back into the report is the
affiliate **sub-ID**, which is baked into the link when it is generated.

| Report | Sub-ID columns | Populated in the real export |
|---|---|---|
| Shopee | `Sub_id1` … `Sub_id5` | **0 / 108** — all empty |
| Lazada | `Aff Sub ID`, `Sub ID 1` … `Sub ID 6` | `Aff Sub ID`: 22/218 = literal `"Unknown"`, rest empty; `Sub ID 1-6`: all empty |

**Consequence:** with links generated as they are today, every report row is
unattributable — the importer can only report them as `unmatched`. There is no
fallback: `Order id` first appears in the report itself, so it cannot be matched
back to a click that happened days earlier.

**Required operational change:** when the moderator generates the affiliate link
in their dashboard, it must carry our sub-ID (both programs expose this; that is
what the columns are for). The link flow stores it on `referral_links.sub_id`
and the importer matches `sub_id -> referral_link -> review -> reviewer`.
A sub-ID identifies the **link/review**, not a single click — every click on one
link shares it, which is why it cannot be the per-click `click_ref`.

## Shopee — Affiliate Commission Report

- Encoding: UTF-8 **with BOM**. 47 columns. One row **per item**, so several rows
  share an `Order id` (observed: up to 7).
- Money: `Affiliate Net Commission(₱)` is what we actually receive (equals
  `Total Order Commission(₱)` while `Affiliate Agreement Fee Rate` is 100%).
  `Purchase Value(₱)` is the buyer's spend, NOT our commission. **35/108 rows are
  ₱0.** There is **no currency column** — PHP is implied.
- Status: `Order Status` = `Completed(97) | Pending(8) | Cancelled(3)`;
  `Affiliate Item Status` = `Completed(95) | Pending(8) | Cancelled(5)`.
  Only **Completed** may be paid — Shopee states pending commissions are only
  paid once the order completes.
- Column names contain `₱` (U+20B1); match them tolerantly.

## Lazada — Conversion Report

- Encoding: **cp1252 / latin-1, NOT UTF-8** (e.g. `Pokémon`, byte `0xe9`).
  47 columns. One row per SKU-order.
- Money: `Payout` is our commission (**74/218 rows are 0**); `Order Amount` is the
  buyer's spend. `Currency` = `PHP` for every row.
- Status: `Status` = `Delivered(162) | Rejected(45) | Returned(11)`;
  `Validity` = `valid(173) | invalid(45)`. Only **valid + Delivered** may be paid.
  `Payment Status` is `-` throughout (unused in this export).
- Order refs: `Check Out ID`, `Sku Order ID`, `Sub Order ID`.

## What the importer must therefore do

1. **Detect the format** from the header (Shopee vs Lazada vs the legacy generic
   contract), rather than demanding one fixed header.
2. **Decode per format** — utf-8-sig for Shopee, cp1252 for Lazada — and never
   reject a file merely for not being UTF-8.
3. **Gate on status**: import only Completed (Shopee) / valid+Delivered (Lazada).
   Everything else is reported as skipped, never paid. Paying a pending or
   cancelled order is a real financial error.
4. **Map money per platform**, and treat ₱0 commission rows as *skipped, not
   invalid* — they are normal (they are ~1/3 of both reports) and must not fail
   the whole file under the all-or-nothing rule.
5. **Match on sub-ID**, falling back to reporting the row as unmatched.
6. Keep the existing idempotency key `(csv_source = filename:sha256[:12],
   row_reference = line number)` and the audit log.

---

## Resolution (M3 slice 12 — implemented 2026-07-16)

**Owner decision: manual CSV only**, permanently, with a first-party brand
partnership as the intended future replacement. No scraping, no proxies, no
headless browsers — unchanged.

"Manual CSV only" turned out to mean **real code**, not "no code": the M2
importer would have rejected both real exports at the header, and if it hadn't,
it would have paid out on pending/cancelled/rejected rows. What shipped:

- `app/services/report_formats.py` — detects `shopee_commission_report`,
  `lazada_conversion_report`, or the legacy `generic_v1` contract from the
  header; decodes per format (utf-8-sig / cp1252); normalises money, status and
  dates; returns payable rows, skipped rows (with reasons), and hard errors.
- `commission_service.import_commissions` accepts any of the three formats and
  matches **sub-ID → referral link → review** first, then the legacy
  `click_ref`, then a known `order_ref`.
- `referral_links.sub_id` + `sub_id_in_url` (migration `0013_referral_sub_id`),
  unique among *active* links. `GET /admin/review-queue` exposes
  `suggested_sub_id`; `POST /admin/reviews/{id}/referral-link` accepts `sub_id`.
- The import response now reports `format` and `skipped_unpayable[]` so a
  moderator can see why a 218-row report imported few rows.

Verified against the real files (`backend/tests/fixtures/`, byte-for-byte):

| Report | Detected | Payable | Skipped | Hard errors | Commission total |
|---|---|---|---|---|---|
| Shopee (108 rows) | ✅ | 64 | 44 (11 pending/cancelled, 31 zero, 2 item-status) | 0 | PHP 1,289.03 |
| Lazada (218 rows) | ✅ | 108 | 110 (45 invalid, 11 status, 54 zero) | 0 | PHP 3,494.74 |

### ⚠️ Still required of the operator — attribution

Both real exports carry **no sub-ID**, so every payable row above imports as
`unmatched` and nobody is paid. That is correct behaviour (never guess who earned
money), but it means **reconciliation does not work until the moderator starts
generating affiliate links with our sub-ID**:

1. Open the review's queue card and copy `suggested_sub_id` (e.g. `blt_1a2b3c…`).
2. Paste it into the sub-ID field of the Shopee/Lazada affiliate link generator
   (Shopee fills `Sub_id1`, Lazada fills `Aff Sub ID`).
3. Paste the generated link back. `sub_id_in_url: false` in the response means
   the link does not visibly carry it — expect that row to come back unmatched.

Links created before this change were backfilled with their deterministic
sub-ID, so they will attribute if a future report ever carries one.
