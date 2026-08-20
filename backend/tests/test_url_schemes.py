"""A user-supplied URL that something later renders as a link is script execution.

`ReportCreate.evidence_url` had this right, with the reasoning written out: a
reporter-supplied string that a *moderator* clicks is stored XSS running in the
moderator's session. The reasoning was right and the placement was wrong. It
guarded one field, while `products.source_url` and `review_requests.source_url`
carried the same kind of string to the same moderator queue behind nothing but
a length cap — and `ModerationQueue.tsx` renders the product one as `href`
directly.

The last test here is the one that matters over time: it fails when a new
`*_url` field appears on a request schema without going through the guard, so
this cannot be re-learned a third time.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import pytest
from pydantic import BaseModel, ValidationError

from app.models.enums import ModerationReason
from app.schemas.product import ProductCreate
from app.schemas.report import ReportCreate
from app.schemas.request_board import RequestCreate
from app.schemas.urls import web_url_or_none

# The interesting schemes are the ones nobody thinks of, which is why the
# implementation allowlists rather than blocklists.
DANGEROUS = [
    "javascript:alert(1)",
    "JavaScript:alert(1)",          # scheme matching is case-insensitive
    "  javascript:alert(1)",        # and survives leading whitespace
    "data:text/html,<script>x</script>",
    "vbscript:msgbox(1)",
    "blob:https://example.com/uuid",
    "filesystem:https://example.com/temporary/x",
    "file:///etc/passwd",
]

GUARDED = [
    (ProductCreate, {"name": "Widget"}, "source_url"),
    (RequestCreate, {"title": "t", "details": "d"}, "source_url"),
    (ReportCreate, {"reason": ModerationReason.spam}, "evidence_url"),
]


@pytest.mark.parametrize("model,base,field", GUARDED,
                         ids=lambda v: v.__name__ if inspect.isclass(v) else "")
@pytest.mark.parametrize("bad", DANGEROUS)
def test_dangerous_schemes_are_refused(model, base, field, bad):
    with pytest.raises(ValidationError):
        model(**base, **{field: bad})


@pytest.mark.parametrize("model,base,field", GUARDED,
                         ids=lambda v: v.__name__ if inspect.isclass(v) else "")
def test_ordinary_links_still_work(model, base, field):
    obj = model(**base, **{field: "https://shopee.ph/product-i.123.456"})
    assert getattr(obj, field) == "https://shopee.ph/product-i.123.456"
    assert model(**base, **{field: "http://example.com"})


@pytest.mark.parametrize("model,base,field", GUARDED,
                         ids=lambda v: v.__name__ if inspect.isclass(v) else "")
@pytest.mark.parametrize("blank", [None, "", "   "])
def test_blank_means_not_provided(model, base, field, blank):
    """Different from "provided and bad" - only the second is worth refusing."""
    assert getattr(model(**base, **{field: blank}), field) is None


def test_the_helper_reports_which_field_was_wrong():
    with pytest.raises(ValueError, match="Listing links"):
        web_url_or_none("javascript:x", field="Listing links")


class TestEveryUrlFieldIsGuarded:
    """The standing check. A new *_url field must opt in, or this fails."""

    # Reviewed exceptions, each with the reason it does not need the guard.
    ALLOWED = {
        # Admin-only, and constrained far more tightly than a scheme check:
        # referral_service validates it against settings.affiliate_domains.
        ("referral.AttachLinkRequest", "url"),
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
                                           "Patch", "Submit"))):
                    out[f"{m.name}.{name}"] = obj
        return out

    def test_no_unguarded_url_field(self):
        unguarded = []
        for name, model in self._request_schemas().items():
            for field in model.model_fields:
                if not (field == "url" or field.endswith("_url")):
                    continue
                if (name, field) in self.ALLOWED:
                    continue
                try:
                    model.model_validate(
                        {**{f: "x" for f, i in model.model_fields.items()
                            if i.is_required() and f != field},
                         field: "javascript:alert(1)"})
                except ValidationError as exc:
                    if any(e["loc"] == (field,) for e in exc.errors()):
                        continue  # refused on this field: guarded
                unguarded.append(f"{name}.{field}")

        assert not unguarded, (
            f"{unguarded} accept a javascript: URL. Add the validator from "
            f"app/schemas/urls.py, or add it to ALLOWED with the reason.")
