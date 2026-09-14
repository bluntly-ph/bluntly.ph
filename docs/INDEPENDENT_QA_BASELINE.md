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

## Memory

*In progress.* One clean Chromium; heap used/total, DOM nodes, listeners,
Playwright process working set, long tasks, resources and transfer, captured
after load, after 30 s idle, across three laps of Home → Search → Review
detail → Write Review → Seller page (not on the baseline) → Home, and after a
final idle. No leak is claimed without measurements that show one.
