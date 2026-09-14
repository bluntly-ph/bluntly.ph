# Independent QA baseline — 2026-09-14

## Status

- **INDEPENDENT QA: ACTIVE — 11 ISSUES REPORTED SO FAR**
- **QA TRACKER: PENDING COMPLETE HANDOFF**
- **PRODUCTION BASELINE: FROZEN FOR QA**
- **SELLER/PRICE ENGINEERING: CONTINUING OFF-PRODUCTION**
- **PERFORMANCE: INVESTIGATION OPEN — LIGHTHOUSE RUN NEEDS CLEAN REPRODUCTION**

Not claimed: ready for release, QA passed, performance regression confirmed.

## INDEPENDENT_QA_BASELINE_SHA

| Field | Value | Evidence |
|---|---|---|
| **INDEPENDENT_QA_BASELINE_SHA** | `4e7c24247d2cb4d853e58ac6bf6a8d9ce63fadd7` | the SHA on both rows below |
| origin/main | `4e7c24247d2cb4d853e58ac6bf6a8d9ce63fadd7` | `git ls-remote origin refs/heads/main` at 2026-09-14T01:21:39Z |
| Production deployment | GitHub deployment `6422454217`, environment `Production`, sha `4e7c24247d2c`, state `success`, created 2026-09-13T14:11:05Z by `vercel[bot]`, `https://bluntly-czcfv6gke-bluntlyph.vercel.app` | `gh api repos/bluntly-ph/bluntly.ph/deployments?environment=Production` and its statuses |
| Convergence | main == latest successful Production deployment | same SHA on both |
| Live response | `https://www.bluntly.ph/` served from `sin1` (`X-Vercel-Id: sin1::sin1::82p52-…`), `Date: Mon, 14 Sep 2026 01:21:47 GMT` | `curl -D -` |
| Recorded at | 2026-09-14T01:21:39Z | |

**CI on the baseline** — run `34761871674`: Frontend ✓, Backend (no database) ✓,
Production guard ✓, Backend (isolated database) ✗ with 1469 passed, 1 failed,
58 errors. All 59 are classified **TEST/HARNESS**, none implicate product code
on the baseline: the failure is a tripwire pinning the July seller descope, the
errors are a cron-credential fixture colliding with a row a cancelled run left
in the cumulative CI database. Both are fixed in `198e245`, off-production.

**What the baseline does and does not contain.** It carries migration file
0042 and the seller models, with no seller routes or UI. The seller pages, the
Sellers search tab, the enabled "Rate a Seller" action, the claim queue, and
price moderation are all **not** in production.

## The freeze

- No push to `main` while QA gathers evidence. Every push to `main` deploys
  production before CI (Vercel), so a push is a deploy.
- Engineering continues on `feat/moderation-priority-contract` locally and on
  the `sellers-reinstatement` branch, whose CI runs by `workflow_dispatch`
  (the isolated-database job does not run on pull requests). Pushes to a
  non-main branch make Vercel previews, not production.
- The freeze breaks only for a critical P0 production defect. If it does,
  this file records that the independent pass restarts against the new SHA.

Held off-production at the time of recording:

| Commit | What | Where |
|---|---|---|
| `5543062` | QA-001..012 harness and results | local + `sellers-reinstatement` |
| `cb0ed79`, `94d4fd3` | seller rules and API | local + branch |
| `3f50b4e` | OpenAPI field-for-field contract test | local + branch |
| `30b17cd` | 0043 seller review content, removal | local + branch |
| `58b2769`, `72021d9` | seller profile, composer, Sellers tab, claim queue | local + branch |
| `198e245` | CI harness fixes (tripwire, cron fixture) | local + branch — CI run `34794562581` |
| `a37d0ca` | matrix FR-4 rows, conflict C-5 | local |
| `a6183cb` | 0044 price moderation, composer price → observation | local |

## QA issue import — awaiting the tracker

Eleven issues reported; the entries themselves have not arrived. None are
guessed from the summary, and no product code has been changed in anticipation
of them.

| QA ID | Tester wording (verbatim) | Route | Viewport / device | Steps | Expected | Actual | Evidence | Baseline SHA | Classification | Severity | Owner | Fix SHA | Retest |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| — | *pending tracker handoff* | | | | | | | `4e7c242` | | | | | |

Classification is exactly one of: PRODUCT DEFECT · QA HARNESS / TEST
EXPECTATION DEFECT · PERFORMANCE REGRESSION · ENVIRONMENT / EXTERNAL ISSUE ·
DUPLICATE / ALREADY FIXED (with evidence). Tester wording is kept apart from
engineering analysis.

## Lighthouse — the supplied run

`Downloads/www.bluntly.ph-20260914T071726.html`, read-only.

| | |
|---|---|
| Lighthouse | 13.4.1, fetched 2026-09-13T23:17:26Z |
| Form factor / throttling | **desktop**, simulated (RTT 40 ms, 10 Mbps, CPU ×1) |
| Browser | Chrome 152, Windows |
| Scores | Performance 69 · Accessibility 96 · Best Practices 100 · SEO 100 |
| Metrics | FCP 2.4 s · LCP 2.4 s · Speed Index 4.8 s · TBT 0 ms · CLS 0.014 · TTI 2.4 s |
| Requests | 31, ~300 KB transferred |

**Contaminated by an extension.** `chrome-extension://gighmmpiobklfepjocnamgkkbiglidom/…`
(an ad-filtering extension: `globals-front.js`, `content-main.js`,
`polyfill.js`, `cookie-banner-detection.preload.js`, …) is the whole of the
*unused JavaScript* and *unminified JavaScript* findings — ~79 KB unused and
~74 KB unminified. None of it is Bluntly code, and none of it will be optimised.

**Bluntly-owned candidates**, to investigate only after a clean reproduction:

- render-blocking stylesheet `/_next/static/chunks/1qaq7sgotaj6b.css`
  (15,249 B) — `render-blocking-insight`
- `/_next/static/chunks/29qf0wjmceuhq.js`, ~14,001 B estimated legacy
  JavaScript — `legacy-javascript-insight`
- **8 font files** on the homepage (`/_next/static/media/*.woff2`, 5.8–8.8 KB
  each, ~63 KB together). Source: `app/layout.tsx` loads Poppins at six
  weights (200, 300, 400, 500, 600, 700) plus Bebas Neue. Measured usage in
  `app/` and `components/`: `font-extralight` 1 class, `font-light` 25,
  `font-normal` 12, `font-medium` 140, `font-semibold` 166, `font-bold` 71.
  Weight 200 is the only near-unused one, which would save one ~8 KB file.
  Recorded, not changed.
- Speed Index 4.8 s (score 0.04), the weakest metric; FCP scores 0.16
- `lcp-breakdown-insight`: time to first byte 66 ms, **element render delay
  8,778 ms** (observed trace) — the render delay, not the network, is where the
  LCP time goes. **The LCP element is the hero headline** `<h1>` "Finally.
  Honest reviews.", selector `section.relative > div.relative >
  div.animate-fade-up > h1`. It sits inside an entrance animation, so the
  largest paint cannot land until that animation reveals it. Leading
  hypothesis for both the LCP render delay and the 4.8 s Speed Index; to be
  confirmed against the clean runs before anything changes.
- `bf-cache`: "main resource has `cache-control: no-store`" and "a JavaScript
  network request received `Cache-Control: no-store`". Lighthouse marks both
  not actionable; the first follows from the root layout reading the `theme`
  cookie (`app/layout.tsx`), which makes every page dynamically rendered.
- Accessibility `color-contrast` fails on 10 nodes, and they are design
  tokens, not one-offs:

  | Ratio | Foreground / background | Node |
  |---|---|---|
  | 3.44 | `#ffffff` on `#ef5821` | a pill badge (`absolute -top-3 right-3 … bg-[var(--accent…`) |
  | 2.39 | `#9e9e9e` on `#f2f2f2` | `text-[var(--text-muted)]` 12px caption |
  | 4.30 | `#3771c8` on `#f2f2f2` | `text-[var(--accent-trust)]` 12px uppercase label |
  | 4.30 | `#3771c8` on `#f2f2f2` | a 13px link to `/search` |
  | 3.08 | `#ef5821` on `#f2f2f2` | a link to `/search` (`min-h-[44px]`) |
  | 3.08 | `#ef5821` on `#f2f2f2` | 16px semibold `text-[var(--accent-primary)]` paragraph |
  | 2.47 | `#fce1d7` on `#f16937` | `text-white/80` 12px uppercase label |
  | 3.05 | `#fdeee9` on `#ef5821` | `text-white/90` 15px paragraph |
  | 3.78 | `#ffffff` on `#e3541f` | the `/reviews/new` pill |
  | 2.29 | `#8f8f8f` on `#d9d9d9` | `text-[var(--text-muted)]` 12px text |

  Brand orange `#ef5821` fails 4.5:1 both as text on the page colour and as a
  background under white. Recorded, **not changed** during the freeze: it is a
  brand-token decision, and it may already be one of the eleven tracker items.

## Clean reproduction — 2026-09-14, against the baseline

Lighthouse 13.4.1 CLI, Playwright's Chromium (build 1234, `HeadlessChrome/151`,
Lighthouse benchmark index 1445 on this machine), `--headless=new
--disable-extensions`, a fresh profile per run, logged out, public homepage.
Mobile at Lighthouse defaults; desktop with `--preset=desktop`, the same form
factor and simulated throttling as the supplied run. Six runs interleaved
mobile/desktop between 01:26:46Z and 01:28:07Z. No run reported a
`runtimeError`, and none contains extension scripts.

Each CLI invocation exits 1: chrome-launcher cannot delete its temporary
profile on Windows (`EPERM … Temp\lighthouse.*`) **after** the report is
written. An environment artifact of the tool, not a failed run.

| Run | Performance | FCP | LCP | Speed Index | TBT | CLS | Requests / KB |
|---|---|---|---|---|---|---|---|
| mobile-1 | 93 | 1.18 s | 3.02 s | 2.06 s | 142 ms | 0 | 38 / 322 |
| mobile-2 | 94 | 1.27 s | 2.96 s | 2.19 s | 63 ms | 0 | 36 / 322 |
| mobile-3 | 96 | 1.07 s | 2.76 s | 1.32 s | 42 ms | 0 | 37 / 323 |
| **mobile median** | **94** | **1.18 s** | **2.96 s** | **2.06 s** | **63 ms** | **0** | |
| desktop-1 | 98 | 0.56 s | 1.07 s | 1.02 s | 1 ms | 0 | 54 / 324 |
| desktop-2 | 100 | 0.31 s | 0.64 s | 0.73 s | 0 ms | 0 | 54 / 332 |
| desktop-3 | 99 | 0.54 s | 0.93 s | 0.65 s | 0 ms | 0 | 55 / 334 |
| **desktop median** | **99** | **0.54 s** | **0.93 s** | **0.73 s** | **0 ms** | **0** | |

Raw reports: `docs/qa-evidence/lighthouse-2026-09-14/*.report.json.gz` (all
six, gzip; open in the Lighthouse viewer). HTML copies were not committed.

**What this shows, and what it does not.**

- The supplied Performance 69 / Speed Index 4.8 s is **not reproduced** in a
  clean browser. Under the same desktop preset the median is 99 and Speed
  Index 0.73 s. That is consistent with the extension's ~150 KB of injected
  script and the state of the testing machine. It does **not** show that the
  tester's "the site became slower" is wrong: that report is about their
  session, and the memory measurement below is what can speak to it. Nothing
  here is classified as a regression, confirmed or ruled out, until then.
- The Bluntly-owned candidates are present in **every** clean run:
  `1qaq7sgotaj6b.css` render-blocking; ~14.0 KB legacy JavaScript in
  `29qf0wjmceuhq.js`; 8 font files; `bf-cache` failing.
- **Mobile LCP (median 2.96 s) is the one metric outside "good" (≤ 2.5 s),**
  and in every run the LCP element sits inside `.animate-fade-up`: the hero
  `<h1>` on all three desktop runs and on mobile-3, and the featured review
  card's excerpt (`div.animate-fade-up.delay-2 … p.mt-2`) on mobile-1 and
  mobile-2. Element render delay 0.75–1.59 s against a time to first byte of
  99–159 ms. Candidate, **not applied**: stop animating the hero copy and the
  featured card from `opacity: 0`, then re-measure with the same six runs.
- `color-contrast`: 8 failing nodes on mobile, 11 on desktop (the supplied run
  had 10). Brand-token decision; recorded above, not changed.

## Network activity after load (no loop found)

A first memory-probe pass could not start: `page.goto('/', { waitUntil:
'networkidle' })` timed out at 45 s. Measured instead of assumed:

- In the 20 s after `load` (760 ms) the homepage makes 31 requests, **all
  within ~1.2 s**: Next.js link prefetches (`/search` ×6 for its distinct
  query strings, `/login` ×3, `/feed`, `/categories`, `/questions`,
  `/requests`, several `/reviews/<id>`) and the chunks they need. **Zero
  requests in the last 10 s.** No polling, beacon, or refetch loop.
- Exactly one request never completes in the browser: the prefetch of
  `/login?next=%2Freviews%2Fnew`, reached because the "Write a review" link's
  prefetch of `/reviews/new` answers `307` to logged-out visitors. That open
  request is why the page never reaches network-idle.
- The server does not hang: the same URL answers `200` in 0.19–0.23 s with a
  complete body as a plain GET, as an RSC request, and as an RSC prefetch
  (`curl`). The stream is held open client-side, consistent with the router
  not consuming a prefetched redirect target to the end. Recorded as an
  observation, **not** classified as a product defect; one open request is not
  a memory cost of any size.

## Memory

One headless Playwright Chromium, extensions disabled, 1366×900, against the
baseline. Heap and DOM figures are taken **after a forced garbage collection**
(`HeapProfiler.collectGarbage`), so they show retained memory, not garbage
waiting to be collected. Working set is the sum over the Playwright Chromium
processes only (never the tester's own Chrome). Navigation is client-side
through the Next router wherever the app allows it. Script:
`memory-probe.mjs` (session scratchpad); raw JSONL kept alongside it.

**Tour — 2026-09-14 01:32–01:39Z**, three laps of Home → Search (`?q=fan`) →
Review detail → Write Review → a seller URL → Home:

| Snapshot | Heap used / total | DOM nodes | Listeners | Docs | Long tasks | Working set |
|---|---|---|---|---|---|---|
| home, after load | 3.04 / 3.50 MB | 600 | 364 | 2 | 0 | 291 MB |
| home, after 30 s idle | 3.09 / 3.75 MB | 600 | 364 | 2 | 0 | 270 MB |
| lap 1 → review detail | 4.20 / 4.80 MB | 588 | 400 | 2 | 0 | 281 MB |
| lap 1 → home | 3.41 / 3.75 MB | 544 | 355 | 2 | 0 | 286 MB |
| lap 2 → review detail | 3.91 / 4.25 MB | 539 | 374 | 2 | 0 | 279 MB |
| lap 2 → home | 3.41 / 3.75 MB | 544 | 355 | 2 | 0 | 289 MB |
| lap 3 → review detail | 3.91 / 4.25 MB | 539 | 374 | 2 | 0 | 280 MB |
| lap 3 → home | 3.40 / 4.00 MB | 544 | 355 | 2 | 0 | 291 MB |
| home, final after 30 s idle | 3.41 / 4.00 MB | 544 | 355 | 2 | 0 | 282 MB |

- **No growth signal.** Lap 2 and lap 3 are identical at every stop (home
  3.41 MB / 544 nodes / 355 listeners; review detail 3.91 MB / 539 / 374).
  Documents stay at 2, so no detached frame or document is accumulating.
- **No work while idle.** Zero long tasks anywhere; no requests during either
  30 s idle window (26 during first load are prefetches, see above).
- **Two limits on this tour, stated rather than smoothed over:**
  - *Write Review was not measured.* `/reviews/new` redirected to `/login` in
    both the logged-out and the "signed-in" pass: the saved session had
    expired. Measuring the composer needs a fresh human sign-in
    (HUMAN_AUTH_REQUIRED); no credentials are entered by automation.
  - *The seller URL forces a full document load* (resources reset from 87 to
    55): `/sellers/*` is not on the baseline and its 404 is a hard navigation.
    So each lap starts from a fresh document, which would hide slow
    accumulation across laps. A reload-free soak follows.

**Soak — one document, no reloads.** Client-side Home → Search → Review detail
→ Home, logged out: 10 laps (01:46–01:50Z), then 40 laps (01:54–02:06Z). At
each return to Home, after GC (40-lap run):

| Lap | Heap used | DOM nodes | Listeners | Docs | Resource entries | Working set |
|---|---|---|---|---|---|---|
| 5 | 4.85 MB | 598 | 389 | 2 | 113 | 302 MB |
| 10 | 5.10 MB | 598 | 389 | 2 | 158 | 303 MB |
| 15 | 5.19 MB | 598 | 389 | 2 | 203 | 311 MB |
| 20 | 5.26 MB | 598 | 389 | 2 | 250 | 325 MB |
| 25 | 5.35 MB | 598 | 389 | 2 | 250 | 325 MB |
| 30 | 5.40 MB | 598 | 389 | 2 | 250 | 330 MB |
| 35 | 5.43 MB | 598 | 389 | 2 | 250 | 330 MB |
| 40 | 5.47 MB | 598 | 389 | 2 | 250 | 334 MB |
| final, 30 s idle | 5.47 MB | 598 | 389 | 2 | 250 | 326 MB |

- **DOM nodes, listeners and documents are flat for 40 laps.** No detached
  DOM, no duplicated listeners, no leaked frames.
- **Retained heap grows and flattens.** +0.25 MB over laps 5–10, then +0.09,
  +0.07, +0.09, +0.05, +0.03, +0.04 per five laps; by laps 35–40 about
  0.01 MB a lap. That shape is a cache filling toward a bound, not a leak — the
  resource-timing buffer, for one, stops at 250 entries at lap 20, which is
  where working-set growth slows too. The 10-lap run agreed (4.42 → 5.12 MB).
- **No work in the background.** Two long tasks, both at first load, none
  during navigation. Zero requests in either idle window; the 273 requests
  over 40 laps (~7 a lap) are route payloads, prefetches and search
  suggestions, all on navigation.
- **Conclusion from these measurements: no memory leak found, no memory
  regression established.** Not claimed: that the tester's "RAM usage
  increased" is wrong for their session. Their browser carried an
  ad-filtering extension, and these runs are headless, logged out, and do not
  cover Write Review (session expired, above).
