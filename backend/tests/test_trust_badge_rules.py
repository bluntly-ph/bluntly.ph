"""The public trust badge (completion contract X.2), checked without a database.

The contract: a trust badge only after **proof + checks + moderation**, never
on a proof photo alone and never on the author's trust level. Before this, the
public "Verified purchase" mark read `verification_status`, which is set at
submission the moment the author's own photo is attached — before any
moderator has looked at the review.

`has_trust_badge` is decided once, on the API, so every surface shows the same
answer:

* **proof** — `verification_status == verified` (the photo is the author's own
  upload, checked server-side);
* **checks and moderation** — a moderator's decision is recorded on the review:
  `earn_eligible_status` is approved, monetized, or routed to the Honesty Fund,
  which is the decision the moderator makes after reading the fraud and
  duplicate signals on the queue card;
* **published** — the review is live.

Honesty Fund reviews (the approved <=2-star route) keep the badge. Withholding
it only from negative reviews would make honest criticism look less credible,
which is the opposite of what the Honesty Fund exists for (matrix conflict C-6).
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.models.enums import EarnEligibleStatus, VerificationStatus
from app.services.trust_badge import has_trust_badge

NOW = datetime.now(UTC)


def _review(verification=VerificationStatus.verified, published=True,
            status=EarnEligibleStatus.approved, stars=4):
    return SimpleNamespace(verification_status=verification,
                           published_at=NOW if published else None,
                           earn_eligible_status=status, star_rating=stars)


@pytest.mark.parametrize("status", [EarnEligibleStatus.approved, EarnEligibleStatus.monetized,
                                    EarnEligibleStatus.honesty_fund])
def test_proof_moderation_and_publication_earn_the_badge(status):
    assert has_trust_badge(_review(status=status)) is True


def test_a_photo_alone_does_not():
    # Published with no recorded moderator decision (legacy / direct publish).
    assert has_trust_badge(_review(status=EarnEligibleStatus.none)) is False


def test_moderation_without_proof_does_not():
    assert has_trust_badge(_review(verification=VerificationStatus.unverified)) is False


@pytest.mark.parametrize("status", [EarnEligibleStatus.pending, EarnEligibleStatus.rejected])
def test_an_undecided_or_rejected_review_does_not(status):
    assert has_trust_badge(_review(status=status)) is False


def test_an_unpublished_review_does_not():
    assert has_trust_badge(_review(published=False)) is False


def test_an_honest_negative_review_keeps_it():
    assert has_trust_badge(_review(status=EarnEligibleStatus.honesty_fund, stars=1)) is True


def test_the_public_review_shape_carries_it():
    from app.schemas.review import ReviewOut

    assert "has_trust_badge" in ReviewOut.model_computed_fields
