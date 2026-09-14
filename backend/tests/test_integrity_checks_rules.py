"""External integrity checks — plagiarism and reverse image (FR-8 layers 2 and 3).

The PRD names no provider for either (layer 3 is marked [AMBIGUOUS]), and no
adapter ships for any. The completion contract: build the interface, the
status and the moderator visibility, and report EXTERNAL_SERVICE_REQUIRED rather
than fabricate a successful check. So the rule pinned here is honesty:

* with no provider, each external check reads **not_configured** — never
  "clear", which a moderator would take as a pass;
* naming a provider in configuration does not make checks run: with no adapter
  it is still not configured, and the status says why;
* the internal duplicate-content signal (trigram similarity against published
  reviews) is reported as its own layer, clear or flagged, so it is not
  mistaken for the external plagiarism check it is not.
"""

from __future__ import annotations

from app.services.integrity_checks import check_statuses, provider_status
from tests.test_seller_api_contract import _required_roles, _routes


def test_with_no_provider_both_external_checks_say_so():
    status = provider_status(plagiarism_provider="none", reverse_image_provider="none")
    assert status.plagiarism.configured is False
    assert status.plagiarism.provider is None
    assert status.reverse_image.configured is False
    assert status.reverse_image.provider is None


def test_naming_a_provider_without_an_adapter_is_still_not_configured():
    status = provider_status(plagiarism_provider="copyleaks", reverse_image_provider="tineye")
    assert status.plagiarism.configured is False
    assert status.plagiarism.provider == "copyleaks"
    assert "no adapter" in status.plagiarism.detail.lower()
    assert status.reverse_image.configured is False


def test_a_review_card_reports_every_layer_without_claiming_a_pass():
    flagged = check_statuses(duplicate_content=True)
    assert flagged.internal_duplicate == "flagged"
    assert flagged.plagiarism == "not_configured"
    assert flagged.reverse_image == "not_configured"
    assert check_statuses(duplicate_content=False).internal_duplicate == "clear"


def test_the_queue_card_carries_the_external_statuses_beside_the_frozen_signals():
    from app.schemas.referral import QueueIntegrityChecks, QueueItem, QueueSignals

    # The advisory six stay frozen (test_telemetry_isolation); these sit beside them.
    assert "integrity" in QueueItem.model_fields
    assert not {"plagiarism_status", "reverse_image_status"} & set(QueueSignals.model_fields)
    checks = QueueItem.model_fields["integrity"].get_default(call_default_factory=True)
    assert isinstance(checks, QueueIntegrityChecks)
    assert checks.plagiarism_status == "not_configured"
    assert checks.reverse_image_status == "not_configured"


def test_the_provider_status_is_moderator_only():
    route = _routes()[("GET", "/api/v1/admin/integrity-providers")]
    roles = _required_roles(route)
    assert "moderator" in roles
    assert "user" not in roles
