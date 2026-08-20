# BUG-030 — what "verified" claims, and what it means

Evidence only. Two decisions at the end are the owner's; neither is taken here,
because both change a public trust claim.

## The facts

All six published reviews in production, checked 2026-08-20:

| | value |
|---|---|
| `verification_status` | `verified` — all six |
| `photo_url` set | yes — all six |
| photo stored in our `review-photos` bucket | **no — none of them** |
| `receipt_key` | none |
| moderation log entries | zero |
| `earn_eligible_status` | 4 `monetized`, 1 `approved`, 1 `honesty_fund` |

They were written directly by `seed_showcase.py`, which sets
`verification_status` and `published_at` itself rather than going through
submission and moderation.

## What the contract says

PRD FR-3, line 64:

> Reviews **publish immediately**; photograph at submission ⇒ *verified*
> status; no photo ⇒ *unverified*, no earning eligibility.

So the platform's own bar for `verified` is **a photograph was attached at
submission**. Not that a receipt was checked, not that a moderator approved it.
The receipt is separately described as *optional post-publish supporting
evidence for earn_eligible evaluation* — which puts proof-of-purchase evidence
at a different, later stage than the `verified` flag.

By that definition the six showcase reviews are not mislabelled: they have
photographs.

## The finding this turned up instead

`components/review/ReviewDetail.tsx:192` renders the flag as:

> ✅ **Verified purchase**

The state means "a photograph was attached". The badge asserts a *purchase was
verified*. Those are different claims, and the second is stronger than anything
the platform checks — a photograph at submission does not establish that a
purchase occurred, which is presumably why the PRD keeps the receipt as a
separate signal.

**This applies to every review on the platform, not just the seeded six.** A
real reviewer who attaches any product photograph gets a badge telling readers
their purchase was verified.

The gap matters because the badge is the product's central promise. The PRD
opens by positioning bluntly against marketplaces where there is "no proof of
purchase required" — so a badge that says "Verified purchase" on the strength
of an attached photo is claiming exactly the thing the platform exists to fix.

## What the flag actually drives

| Consumer | Effect |
|---|---|
| `ReviewDetail.tsx:192` | The public "Verified purchase" badge |
| `referral_service.py:135` | **Gates monetization** — "Only verified reviews (proof photo) can be monetized" |
| `trust_service.py:74` | `verified_count` feeds the author's trust stage and reputation |
| `products.py:78` | `verified_review_count`, rendered by the FR-2 comparison tool |
| `OnboardingWizard.tsx` | `verifiedReviewCount` |

## Exact consequences of flipping the six to `unverified`

- All six lose the public badge.
- **FR-2 comparison shows `0` verified reviews for all six products.** The
  comparison tool's verified-review column would read zero across the board,
  which is most of what that column is for during acceptance.
- The showcase authors' trust stage and reputation recalculate downward.
- **It creates an inconsistency rather than removing one.** Four of the six are
  `earn_eligible_status = monetized`, and `referral_service` holds that only a
  verified review can be monetized. Flipping verification alone leaves four
  reviews in a state the code says is unreachable. A consistent change has to
  address both fields.

## Related: the code no longer produces this state

`_verification_for()` now requires the photo to be an object the author
uploaded to the `review-photos` bucket, because "any non-empty string" meant a
reviewer could paste a stranger's photo and be verified for it. Under that
rule, none of the six would be verified today — their photos are not in the
bucket.

So `seed_showcase.py` now writes a state the application itself would refuse to
derive. That is not a security problem — the seed script is trusted and run by
hand — but it does mean the showcase no longer demonstrates the real rule.

## Owner decisions

**1. The badge wording.** Does "Verified purchase" overstate a flag that means
"a photograph was attached"? If it does, the honest options are to soften the
badge (e.g. "Photo provided", "Proof photo attached") or to raise the bar so
the flag means what the badge says (require a receipt for it). This affects
every review and is a change to a public trust claim, so it is not made here.

**2. The showcase six.** If the badge wording is corrected, they need no
change — they satisfy the contract's definition. If the bar is raised to
require a receipt, they stop qualifying, and the choice is between giving them
real receipts, labelling them visibly as showcase content, or accepting a
comparison tool that reads zero.
