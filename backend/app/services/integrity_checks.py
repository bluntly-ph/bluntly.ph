"""External integrity checks — plagiarism and reverse image (FR-8 layers 2 and 3).

The PRD names no provider for either check (layer 3 is marked [AMBIGUOUS]), and
none is procured. This module is the seam a provider plugs into, and until one
does it reports that honestly:

* each external check is **not_configured** — never "clear", which a moderator
  would read as a pass;
* naming a provider in configuration is not enough: without an adapter in
  ``TEXT_ADAPTERS`` / ``IMAGE_ADAPTERS`` the check is still not configured, and
  the status says why;
* the internal duplicate-content match (trigram similarity against published
  reviews, ``fraud_service``) is its own layer, so it is never presented as the
  external plagiarism check it is not.

Leaf module: pydantic and typing only, so ``app.schemas`` can import the status
type without a cycle.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol

from pydantic import BaseModel

#: What a queue card shows for one external check. Only an adapter can produce
#: "clear" or "flagged"; with none registered every check is "not_configured".
ExternalCheckStatus = Literal["not_configured", "clear", "flagged"]


class TextCheckProvider(Protocol):
    """A plagiarism provider (FR-8 layer 2)."""

    name: str

    def check_text(self, text: str) -> ExternalCheckStatus: ...


class ImageCheckProvider(Protocol):
    """A reverse image search provider (FR-8 layer 3)."""

    name: str

    def check_images(self, urls: Sequence[str]) -> ExternalCheckStatus: ...


#: Adapters shipped in this build, by the provider name configuration uses.
#: Both are empty: no provider is procured.
TEXT_ADAPTERS: dict[str, TextCheckProvider] = {}
IMAGE_ADAPTERS: dict[str, ImageCheckProvider] = {}


class ProviderState(BaseModel):
    configured: bool
    #: The provider named in configuration, if any — configured or not.
    provider: str | None
    detail: str


class ProviderStatusOut(BaseModel):
    plagiarism: ProviderState
    reverse_image: ProviderState


class CheckStatuses(BaseModel):
    internal_duplicate: Literal["clear", "flagged"]
    plagiarism: ExternalCheckStatus
    reverse_image: ExternalCheckStatus


def _named(value: str | None) -> str | None:
    name = (value or "").strip().lower()
    return None if name in ("", "none") else name


def _state(setting: str, value: str | None, adapters: dict, what: str) -> ProviderState:
    name = _named(value)
    if name is None:
        return ProviderState(configured=False, provider=None,
                             detail=f"No {what} provider is configured, so no {what} check runs.")
    if name not in adapters:
        return ProviderState(configured=False, provider=name,
                             detail=(f"{setting} names {name!r}, but this build has no adapter "
                                     f"for it, so no {what} check runs."))
    return ProviderState(configured=True, provider=name,
                         detail=f"{what.capitalize()} checks run through {name!r}.")


def provider_status(*, plagiarism_provider: str | None,
                    reverse_image_provider: str | None) -> ProviderStatusOut:
    """Whether each external check can run, and why not when it cannot."""
    return ProviderStatusOut(
        plagiarism=_state("PLAGIARISM_PROVIDER", plagiarism_provider, TEXT_ADAPTERS,
                          "plagiarism"),
        reverse_image=_state("REVERSE_IMAGE_PROVIDER", reverse_image_provider, IMAGE_ADAPTERS,
                             "reverse image"),
    )


def check_statuses(*, duplicate_content: bool) -> CheckStatuses:
    """Every integrity layer for one review, as a moderator sees it.

    No external result is stored anywhere, because no check has ever run: both
    external layers are "not_configured". An adapter that lands will need a
    place to keep its results, and this is where the queue will read them.
    """
    return CheckStatuses(
        internal_duplicate="flagged" if duplicate_content else "clear",
        plagiarism="not_configured",
        reverse_image="not_configured",
    )
