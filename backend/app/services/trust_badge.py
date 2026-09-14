"""The public trust badge (completion contract X.2).

A leaf module on purpose: the rule is imported by the review schema, which the
review service imports in turn, so it must depend on nothing but the enums.

The contract's rule is **proof + checks + moderation**, never a proof photo
alone and never the author's trust level:

* proof — `verification_status == verified`: the photo is this author's own
  upload, checked server-side at submission (`review_service._verification_for`);
* checks and moderation — `earn_eligible_status` records a moderator's decision:
  approved, monetized, or routed to the Honesty Fund. A moderator makes that
  decision with the fraud and duplicate-content signals on the queue card;
* publication — `published_at` is set.

The Honesty Fund route keeps the badge. PRD FR-6 attaches the badge to approved
>=3-star reviews; withholding it only from honest negative reviews would make
criticism look less credible than praise, the opposite of what the Honesty Fund
is for (docs/FULL_FEATURE_MATRIX.md, conflict C-6).
"""

from __future__ import annotations

from typing import Any

from app.models.enums import EarnEligibleStatus, VerificationStatus

#: The recorded moderator decisions that admit a review to the badge.
_DECIDED = frozenset({
    EarnEligibleStatus.approved,
    EarnEligibleStatus.monetized,
    EarnEligibleStatus.honesty_fund,
})


def has_trust_badge(review: Any) -> bool:
    """Proof, a moderator's decision, and publication — all three."""
    return (
        review.verification_status == VerificationStatus.verified
        and review.published_at is not None
        and review.earn_eligible_status in _DECIDED
    )
