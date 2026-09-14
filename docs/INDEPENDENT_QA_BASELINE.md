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

## Clean reproduction

*In progress.* Fresh Playwright Chromium, extensions disabled, logged out,
public homepage, 3 mobile + 3 desktop runs at Lighthouse defaults, medians
reported, every raw report kept.

## Memory

*In progress.* One clean Chromium; heap used/total, DOM nodes, listeners,
Playwright process working set, long tasks, resources and transfer, captured
after load, after 30 s idle, across three laps of Home → Search → Review
detail → Write Review → Seller page (not on the baseline) → Home, and after a
final idle. No leak is claimed without measurements that show one.
