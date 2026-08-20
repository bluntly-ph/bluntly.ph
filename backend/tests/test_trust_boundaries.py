"""Nothing a client sends may decide what the platform vouches for.

This is its own audit category because the defects in it do not look like bugs.
Every one so far has been a field that was trusted for what it *implied* rather
than for what it was:

  * `photo_url` was any non-empty string, and a non-empty string meant FR-3
    "verified". A reviewer could paste a stranger's photo, or a URL to nothing,
    and wear the badge for it.
  * `receipt_key` was a storage path the client chose, so possession of a path
    stood in for ownership of the document.

Both were fixed in the route. This file exists because a route is the wrong
place to keep an invariant that a service decides: seed scripts, admin paths
and new endpoints all reach the service directly, and one of them eventually
will. The checks now sit next to the decisions, and these tests pin them there.

The last test is the generalised form: no request schema may declare a field
whose name is a piece of trust, earnings or identity state.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import uuid

import pytest
from pydantic import BaseModel

from app.models.enums import VerificationStatus
from app.services.review_service import _verification_for

AUTHOR = uuid.UUID("11111111-1111-1111-1111-111111111111")
STRANGER = uuid.UUID("22222222-2222-2222-2222-222222222222")
BUCKET = "https://proj.supabase.co/storage/v1/object/public/review-photos"


class TestAProofPhotoMustBeTheAuthorsOwn:
    """FR-3 makes the photo the thing that verifies. So it has to be theirs."""

    def test_the_authors_own_upload_verifies(self):
        url = f"{BUCKET}/{AUTHOR}/abc123.jpg"
        assert _verification_for(url, AUTHOR) is VerificationStatus.verified

    def test_another_users_photo_does_not(self):
        """The forgery: a real, working, publicly readable photo - someone else's."""
        url = f"{BUCKET}/{STRANGER}/abc123.jpg"
        assert _verification_for(url, AUTHOR) is VerificationStatus.unverified

    @pytest.mark.parametrize("url", [
        "https://example.com/some-photo.jpg",
        "https://proj.supabase.co/storage/v1/object/public/product-images/x/y.jpg",
        "not-a-url-at-all",
        f"{BUCKET}/abc123.jpg",                      # no owner folder
        f"{BUCKET}/{AUTHOR}extra/abc123.jpg",        # prefix, not the folder
    ])
    def test_nothing_else_verifies(self, url):
        assert _verification_for(url, AUTHOR) is VerificationStatus.unverified

    @pytest.mark.parametrize("blank", [None, "", "   "])
    def test_no_photo_is_simply_unverified(self, blank):
        assert _verification_for(blank, AUTHOR) is VerificationStatus.unverified

    def test_a_query_string_cannot_smuggle_a_foreign_path(self):
        url = f"{BUCKET}/{STRANGER}/abc.jpg?ignored={AUTHOR}"
        assert _verification_for(url, AUTHOR) is VerificationStatus.unverified

    def test_refusing_to_vouch_is_not_an_exception(self):
        """A caller that ignores the answer must not thereby get 'verified'.

        Returning unverified rather than raising means the failure mode of
        every future caller is the safe one.
        """
        assert _verification_for("https://evil.example/x.jpg", AUTHOR) \
            is VerificationStatus.unverified


class TestNoRequestSchemaCarriesTrustState:
    """The generalised form of both defects, as a standing check.

    A request schema declaring one of these fields is not automatically a bug -
    `RoleUpdate.role` is the moderator endpoint and is correct. But it must be
    a deliberate, reviewed decision, so the allowed set is written down here and
    anything new has to be added on purpose.
    """

    SENSITIVE = {
        "verification_status", "verification_tier", "is_verified",
        "trust_stage", "trust_score", "reputation_score", "seller_trust_score",
        "earn_eligible_status", "monetized",
        "wallet_balance", "token_balance", "balance",
        "is_suspended", "is_removed", "published_at",
        "affiliate_link", "commission_amount", "commission_status",
        "is_first_responder", "is_best_answer",
        "fraud_score", "duplicate_of",
        "author_id", "voter_id", "responder_id", "asker_id", "submitted_by",
        "password_hash", "receipt_url", "avg_rating", "review_count",
    }

    # Reviewed and intended. Each needs a reason, not just an entry.
    ALLOWED = {
        # Moderator-only endpoint; additionally refuses to grant `moderator`
        # itself, so it cannot be used to mint a peer.
        ("user.RoleUpdate", "role"),
        # The client picks which of ITS OWN uploaded objects to attach. The
        # service checks ownership before it means anything - see
        # review_service._own_receipt_key / _verification_for.
        ("review.ReviewCreate", "receipt_key"),
        ("review.ReviewUpdate", "receipt_key"),
    }

    def _request_schemas(self):
        import app.schemas as pkg
        out = {}
        for m in pkgutil.iter_modules(pkg.__path__):
            mod = importlib.import_module(f"app.schemas.{m.name}")
            for name, obj in vars(mod).items():
                if (inspect.isclass(obj) and issubclass(obj, BaseModel)
                        and obj is not BaseModel
                        and name.endswith(("Create", "Update", "In", "Request",
                                           "Patch", "Submit", "Canonicalize"))):
                    out[f"{m.name}.{name}"] = obj
        return out

    def test_every_such_field_is_on_the_reviewed_list(self):
        found = {
            (name, field)
            for name, model in self._request_schemas().items()
            for field in model.model_fields
            if field in self.SENSITIVE | {"role", "status"}
        }
        unreviewed = found - self.ALLOWED
        assert not unreviewed, (
            f"request schema(s) accept trust state without review: "
            f"{sorted(unreviewed)}. If intended, add it to ALLOWED with the "
            f"reason it is safe.")

    def test_the_reviewed_list_has_not_gone_stale(self):
        """An entry for a field that no longer exists hides the next one."""
        schemas = self._request_schemas()
        stale = [(n, f) for n, f in self.ALLOWED
                 if n not in schemas or f not in schemas[n].model_fields]
        assert not stale, f"ALLOWED lists fields that no longer exist: {stale}"
