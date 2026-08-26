# Implementation audit — surfaces against their approved Figma frames

**Prepared 2026-08-26.** Figma file `lso4Ri4hDaZxvCebhUqlY5`.

This is the classification the owner asked for: every surface judged against the
approved frame that exists for it, rather than against a general impression of
whether it looks reasonable.

## How to read this

| Classification | Meaning |
|---|---|
| `FIGMA_1_TO_1` | Built to the frame; differences are sub-pixel or invisible at the frame's own viewport. |
| `MINOR_FIDELITY_GAP` | Recognisably the frame, with specific measurable differences listed. |
| `MAJOR_FIDELITY_GAP` | Different structure or information architecture. Spacing work would not close it. |
| `NO_CURRENT_FIGMA` | No approved frame exists. Built to the design system instead. |
| `SUPERSEDED_BY_OWNER_DECISION` | A frame exists and was deliberately departed from, with the decision recorded. |

**A visual claim requires visual evidence.** Where a surface has not been
rendered and compared, this document says so rather than inferring fidelity
from the source. That distinction is the point of the audit.

---

## Surfaces

| Surface | Frame | Classification | Visual evidence |
|---|---|---|---|
| `/` landing | `1902:1504` | `FIGMA_1_TO_1` | Screenshot-compared at 390/768/1440 in the earlier sprint. |
| `/reviews/[id]` | `4218:1196` | `SUPERSEDED_BY_OWNER_DECISION` | The frame is a phone layout; the owner approved a desktop redesign (site header + 20rem context sidebar from `lg`). Mobile is unchanged and matches. |
| `/feed` | `NO_CURRENT_FIGMA` | — | New surface approved after the frames were drawn. Built from the design system; verified responsive 320–1920. |
| `/dashboard` | `5572:7130` | **Built to frame; visual comparison OUTSTANDING** | Rendered component-by-component against fixture data at 390/768/1440 with zero console errors and no horizontal overflow. **Not yet rendered behind a real login** — see *Outstanding* below. |
| `/moderate` | `5017:1738` | **Built to frame; visual comparison OUTSTANDING** | Same as above, at 1280/768/390. Was `MAJOR_FIDELITY_GAP` before this sprint: the frame is a sidebar console and the page was a single scrolling list. |
| Request Distribution (within `/moderate`) | Owner-supplied reference | `NO_CURRENT_FIGMA` | No Figma frame; built to the reference's information architecture in Bluntly's own design language, deliberately not Vercel's. Rendered and verified in all four states at 390/768/1440. |
| `/login`, `/signup`, `/welcome` | `5357:2982` | `FIGMA_1_TO_1` | Verified in the earlier sprint. |
| `/search`, `/categories`, `/questions`, `/requests` | `NO_CURRENT_FIGMA` | — | Built from the design system. |

---

## Documented deviations

Each is a deliberate departure from an approved frame, with the reason and what
would close it.

### Avg. Read time — `/dashboard`

| | |
|---|---|
| **Figma** | A third stat reading "4m 3s". |
| **Implementation** | `—`, labelled "Not measured yet". |
| **Why** | Nothing measures read time. Producing it means timing how long a reader stays on a page, which is reader-behaviour tracking rather than the aggregate counting used everywhere else here, and it needs a privacy ruling that is the owner's to make. |
| **What would close it** | Either (a) an owner decision permitting reader-session timing, plus a privacy-policy line; or (b) a switch to **estimated reading time derived from content length**, which needs no tracking at all — but it must then be labelled *estimated reading time*, never *average read time*. The two are different claims and must not be conflated. |
| **API shape** | Returns `null` and names the field in `unavailable[]`, so the client renders the tile honestly rather than substituting a plausible number. |

### Unbuilt administrative destinations — `/moderate`

| | |
|---|---|
| **Figma** | Ten navigation items, rendered identically. |
| **Implementation** | The three with a real destination link. The other seven keep their position and label, marked "Soon", and are not focusable. |
| **Why** | Products, Sellers, Reviewers, Affiliate Links, Honesty Fund, Activity Log and Settings have no page behind them. Shipping them as live links would put seven dead controls in an admin tool's primary navigation. |
| **What would close it** | Build the seven screens, or an owner ruling that they are out of scope for this release. |

---

## Outstanding — authenticated visual comparison

`/dashboard` and `/moderate` have **not** been rendered end-to-end behind a real
moderator login by engineering. What has been done:

* every component rendered against fixture data at each required viewport, with
  zero console errors and no horizontal overflow;
* every backing API exercised against production data;
* server-side authorization verified (both routes 307 to `/login?next=…`, every
  new endpoint 401s anonymously).

That is **not** acceptance evidence for a 1:1 claim, and this document does not
make one. The blocker is the browser channel: Claude's Chrome extension reports
no connected browser, and engineering will not mint a production token or
weaken a guard to work around it.

**To close:** connect the browser channel to the already signed-in
`bluntly.ph@gmail.com` moderator session, then compare both pages against their
frames at 1440 / 1280 / 1024 / 768 / 393 with screenshot evidence.

---

## Dashboard data integrity

The dashboard's figures are required to reconcile against the canonical
affiliate system, and the two axes must never be conflated:

```
lifecycle   Pending | Completed | Cancelled | Returned     (what the marketplace says)
settlement  not_earned | earned | paid | reversed          (what our ledger did)
```

They are stored, served and rendered separately, and the admin console shows
them as two independent groups rather than one combined bar. This is not
cosmetic: a `completed` order can be `not_earned` when no review can be
attributed to it, and a `returned` one can be `paid` — that is exactly the
post-payout case the platform absorbs. A single progression bar would assert a
relationship that does not exist, and would visually imply `Completed = paid`.

The reviewer dashboard's headline is **net** recognised commission: reversal
entries are included in the sum rather than filtered out, so a returned sale
reduces the figure instead of leaving a reviewer looking at money they no
longer have.
