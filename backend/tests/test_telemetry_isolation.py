"""Reading telemetry is collection-only: it can never move a score or money.

This module is the permanent boundary described in the approved design (§8, §15).
It has two halves:

* **Static** — the production modules that compute a Wilson score, a trust
  stage, a reputation number, a fraud signal, a moderator queue, a publication
  decision, a vote weight, an Honesty Fund share, or a payout are parsed with
  ``ast`` and must not import ``app.models.telemetry`` or
  ``app.services.reading_telemetry_service``.  The single exception is the vote
  route, which is allowed to call the write-only ``note_vote`` tail *after* the
  vote is already committed — and even there, ``note_vote`` is the only name it
  may touch.  Aliases and relative imports are caught structurally, not by
  grepping prose.

* **Behavioural** — against a real PostgreSQL, the same decision surfaces are
  computed with no telemetry, then again with adversarially extreme telemetry
  (a signed-in and a signed-out reader, both pinned at the 30-minute /
  100%-scroll caps, plus a first-vote-geo bucket), then again after those rows
  are deleted.  All three serialized outputs must be identical.  The DB half
  skips where no isolated PostgreSQL is configured; it is a CI gate.
"""

from __future__ import annotations

import ast
import uuid
from dataclasses import fields as dataclass_fields
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import delete

from tests.conftest import register_and_token, requires_db
from tests.test_votes_api import make_published_review

APP = Path(__file__).resolve().parents[1] / "app"

# The two import roots that no decision module may reach.
FORBIDDEN_MODULES = {
    "app.models.telemetry",
    "app.services.reading_telemetry_service",
}

# Spec §8: every module that computes a score, a rank, a moderator priority, a
# publication decision, a vote weight, a fund share, or a payout.  Paths are
# relative to ``backend/app``.
DECISION_MODULES = (
    "services/ranking.py",
    "services/vote_service.py",
    "services/trust.py",
    "services/trust_service.py",
    "services/trust_rating_service.py",
    "services/admin_overview_service.py",
    "services/referral_service.py",
    "services/fraud_service.py",
    "services/honesty_fund_service.py",
    "services/payout_service.py",
    "services/commission_service.py",
    "services/earnings.py",
    "services/dashboard_service.py",
)

# The vote route writes telemetry (§9.1) and is therefore scanned under a
# narrower rule rather than excluded.
VOTE_ROUTE = "api/v1/routes/reviews.py"
VOTE_ROUTE_ALLOWED_NAME = "note_vote"

# Field names that only exist because a reader was measured.  None of them may
# appear in a moderator-queue schema or a public response.
TELEMETRY_FIELD_NAMES = {
    "anon_ref",
    "reader_ref",
    "impression_id",
    "reader_kind",
    "active_ms",
    "body_active_ms",
    "wall_ms",
    "scroll_milestone",
    "first_vote_at",
    "active_ms_at_first_vote",
    "vote_client_after_ms",
    "average_read_seconds",
}


# --------------------------------------------------------------------------- #
# Static import analysis
# --------------------------------------------------------------------------- #

def _module_name(rel_path: str) -> str:
    return "app." + rel_path[:-3].replace("/", ".")


def _resolve(node: ast.ImportFrom, containing_module: str) -> str | None:
    """Absolute dotted module an ``ast.ImportFrom`` points at, or None.

    Handles ``level`` (relative imports) so ``from . import x`` inside
    ``app.services.foo`` resolves to ``app.services.x``.
    """
    if node.level == 0:
        return node.module
    base = containing_module.split(".")
    # ``level`` counts the containing package as 1.
    base = base[: len(base) - node.level]
    if node.module:
        base = base + node.module.split(".")
    return ".".join(base) if base else None


def _telemetry_imports(source: str, containing_module: str) -> list[tuple[str, set[str]]]:
    """Every telemetry import in ``source`` as ``(module, {imported names})``.

    An ``import app.models.telemetry`` yields an empty name set; a
    ``from app.services.reading_telemetry_service import note_vote`` yields
    ``{"note_vote"}``.
    """
    tree = ast.parse(source)
    hits: list[tuple[str, set[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = alias.name
                if target in FORBIDDEN_MODULES or any(
                    target.startswith(f"{m}.") for m in FORBIDDEN_MODULES
                ):
                    hits.append((target, set()))
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve(node, containing_module)
            if resolved is None:
                continue
            names = {alias.name for alias in node.names}
            if resolved in FORBIDDEN_MODULES:
                hits.append((resolved, names))
            elif any(resolved.startswith(f"{m}.") for m in FORBIDDEN_MODULES):
                hits.append((resolved, names))
            else:
                # ``from app.services import reading_telemetry_service``
                for forbidden in FORBIDDEN_MODULES:
                    pkg, _, leaf = forbidden.rpartition(".")
                    if resolved == pkg and leaf in names:
                        hits.append((forbidden, set()))
    return hits


@pytest.mark.parametrize("rel_path", DECISION_MODULES)
def test_no_decision_module_imports_reading_telemetry(rel_path):
    path = APP / rel_path
    source = path.read_text(encoding="utf-8")
    hits = _telemetry_imports(source, _module_name(rel_path))
    assert hits == [], (
        f"{rel_path} imports reading telemetry {hits}. Telemetry is "
        "collection-only (spec §8): a decision module that can see it can be "
        "made to depend on it by a later edit."
    )


def test_vote_route_only_touches_the_write_only_note_vote_tail():
    """The vote route may write telemetry, and only via ``note_vote``.

    Asserted on the parse tree: it may import
    ``reading_telemetry_service`` (or ``note_vote`` directly), but every
    attribute it reads off that module must be ``note_vote``, and it must not
    import the ORM model at all.
    """
    path = APP / VOTE_ROUTE
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imports = _telemetry_imports(source, _module_name(VOTE_ROUTE))
    module_aliases: set[str] = set()
    for module, names in imports:
        assert module != "app.models.telemetry", (
            "the vote route imports the telemetry ORM model; it only needs the "
            "write-only note_vote tail"
        )
        if module == "app.services.reading_telemetry_service":
            if not names:
                # ``from app.services import reading_telemetry_service``
                module_aliases.add("reading_telemetry_service")
            else:
                assert names <= {VOTE_ROUTE_ALLOWED_NAME}, (
                    f"the vote route imports {names - {VOTE_ROUTE_ALLOWED_NAME}} "
                    "from reading_telemetry_service; only note_vote is allowed"
                )

    # Also catch ``import app.services.reading_telemetry_service as x``.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "app.services.reading_telemetry_service":
                    module_aliases.add(alias.asname or alias.name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in module_aliases:
                assert node.attr == VOTE_ROUTE_ALLOWED_NAME, (
                    f"the vote route calls reading_telemetry_service.{node.attr}; "
                    "only note_vote may be reached from a decision path"
                )


# --------------------------------------------------------------------------- #
# Contract freezes (no database)
# --------------------------------------------------------------------------- #

def test_dashboard_summary_still_pins_average_read_seconds_unavailable():
    from app.services.dashboard_service import DashboardSummary

    by_name = {f.name: f for f in dataclass_fields(DashboardSummary)}
    assert by_name["average_read_seconds"].default is None
    assert "average_read_seconds" in DashboardSummary.__dataclass_fields__["unavailable"].default

    summary = DashboardSummary(
        range_key="7d",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 1, 7),
        estimated_commission=Decimal("0"),
        earned_in_window=Decimal("0"),
        total_views=0,
    )
    assert summary.average_read_seconds is None
    assert "average_read_seconds" in summary.unavailable


def test_dashboard_summary_response_schema_reports_read_time_as_unavailable():
    from app.api.v1.routes.users import DashboardSummaryOut

    assert "average_read_seconds" in DashboardSummaryOut.model_fields
    assert "unavailable" in DashboardSummaryOut.model_fields
    annotation = DashboardSummaryOut.model_fields["average_read_seconds"].annotation
    assert type(None) in getattr(annotation, "__args__", (annotation,))


def _model_field_names(model: type[BaseModel], seen: set[type] | None = None) -> set[str]:
    """Every field name declared anywhere in a Pydantic model tree."""
    seen = seen if seen is not None else set()
    if model in seen:
        return set()
    seen.add(model)
    names: set[str] = set()
    for field_name, info in model.model_fields.items():
        names.add(field_name)
        stack = [info.annotation]
        while stack:
            current = stack.pop()
            if isinstance(current, type) and issubclass(current, BaseModel):
                names |= _model_field_names(current, seen)
            stack.extend(getattr(current, "__args__", ()))
    return names


def test_moderator_queue_schema_carries_no_telemetry_field():
    from app.schemas.referral import ReviewQueueResponse

    leaked = _model_field_names(ReviewQueueResponse) & TELEMETRY_FIELD_NAMES
    assert not leaked, f"the moderator queue schema exposes telemetry fields: {leaked}"


def test_queue_signals_field_set_is_frozen_to_the_advisory_six():
    from app.schemas.referral import QueueSignals

    assert set(QueueSignals.model_fields) == {
        "velocity",
        "collusion",
        "duplicate_content",
        "duplicate_of",
        "author_account_age_days",
        "author_review_count",
    }


# --------------------------------------------------------------------------- #
# Behavioural equality against a real PostgreSQL
# --------------------------------------------------------------------------- #

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


#: Adversarially extreme, but still storable: every millisecond field at the
#: 30-minute cap, scroll at 100%, the checkpoint counter maxed.
_EXTREME = dict(
    active_ms=1_800_000,
    body_active_ms=1_800_000,
    wall_ms=1_800_000,
    scroll_milestone=100,
    checkpoints=16,
    max_seq=15,
    clamped=False,
)


def _flood_extreme_telemetry(db, review_id: uuid.UUID, star_rating: int,
                             signed_in_reader: uuid.UUID) -> None:
    """Write the most decision-relevant-looking telemetry the schema permits.

    A signed-in reader and a signed-out reader, both pinned at the caps and both
    carrying a first-vote stamp, plus a first-vote-geo bucket with an
    implausible count.  If any of this could move a number, this is where it
    would show.
    """
    from app.models.enums import ReaderKind
    from app.models.telemetry import ReviewReadingSession
    from app.models.traffic import ReviewFirstVoteGeoBucket

    now = datetime.now(UTC)
    hour = now.replace(minute=0, second=0, microsecond=0)
    db.add_all([
        ReviewReadingSession(
            impression_id=uuid.uuid4(), review_id=review_id,
            reader_kind=ReaderKind.user, reader_ref=signed_in_reader,
            started_at=now - timedelta(minutes=30), last_seen_at=now,
            first_vote_at=now, active_ms_at_first_vote=1_800_000,
            country="US", word_count_at_view=9, star_rating_at_view=star_rating,
            device_class=3, **_EXTREME,
        ),
        ReviewReadingSession(
            impression_id=uuid.uuid4(), review_id=review_id,
            reader_kind=ReaderKind.anon, anon_ref=uuid.uuid4(),
            started_at=now - timedelta(minutes=30), last_seen_at=now,
            country="US", word_count_at_view=9, star_rating_at_view=star_rating,
            device_class=1, **_EXTREME,
        ),
        ReviewFirstVoteGeoBucket(
            review_id=review_id, bucket_start=hour,
            country="US", region="CA", city="Los Angeles",
            first_vote_count=10_000,
        ),
    ])
    db.commit()


def _purge_telemetry(db, review_id: uuid.UUID) -> None:
    from app.models.telemetry import ReviewReadingSession
    from app.models.traffic import ReviewFirstVoteGeoBucket

    db.execute(delete(ReviewReadingSession).where(
        ReviewReadingSession.review_id == review_id))
    db.execute(delete(ReviewFirstVoteGeoBucket).where(
        ReviewFirstVoteGeoBucket.review_id == review_id))
    db.commit()


@requires_db
def test_wilson_trust_reputation_and_fraud_ignore_telemetry(client):
    """Wilson score, reputation, trust stage, helpfulness ratio and the fraud
    signals are byte-identical across absent / extreme / deleted telemetry."""
    import uuid as _uuid

    from app.db.session import SessionLocal
    from app.models.review import Review
    from app.models.user import User
    from app.services.fraud_service import compute_signals
    from app.services.trust import helpfulness_score
    from app.services.trust_service import recompute_user_trust

    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client, role="moderator")
    up_id, up_token, _ = register_and_token(client)
    down_id, down_token, _ = register_and_token(client)
    ah, mh = _auth(author_token), _auth(mod_token)
    author_id = client.get("/api/v1/auth/me", headers=ah).json()["id"]

    rid, _pid = make_published_review(client, ah, mh, name=f"Iso-{_uuid.uuid4().hex[:6]}")
    assert client.post(f"/api/v1/reviews/{rid}/vote", headers=_auth(up_token),
                       json={"vote": "up"}).status_code == 200
    assert client.post(f"/api/v1/reviews/{rid}/vote", headers=_auth(down_token),
                       json={"vote": "down"}).status_code == 200

    def snapshot() -> dict:
        db = SessionLocal()
        try:
            recompute_user_trust(db, _uuid.UUID(author_id))
            db.commit()
            review = db.get(Review, _uuid.UUID(rid))
            author = db.get(User, review.author_id)
            signals = compute_signals(db, review, author)
        finally:
            db.close()
        public = client.get(f"/api/v1/reviews/{rid}").json()
        trust = client.get(f"/api/v1/users/{author_id}/trust").json()
        return {
            "wilson_score": public["wilson_score"],
            "helpful_votes": public["helpful_votes"],
            "unhelpful_votes": public["unhelpful_votes"],
            "reputation_score": trust["reputation_score"],
            "trust_stage": trust["trust_stage"],
            "helpfulness_ratio": trust["helpfulness_ratio"],
            "signals": signals,
        }

    absent = snapshot()
    # Literal expectations, not only cross-state equality.
    assert (absent["helpful_votes"], absent["unhelpful_votes"]) == (1, 1)
    assert absent["helpfulness_ratio"] == str(helpfulness_score(1, 1))
    assert absent["signals"]["velocity"] is False

    db = SessionLocal()
    try:
        _flood_extreme_telemetry(db, _uuid.UUID(rid), 4, _uuid.UUID(up_id))
    finally:
        db.close()
    extreme = snapshot()

    db = SessionLocal()
    try:
        _purge_telemetry(db, _uuid.UUID(rid))
    finally:
        db.close()
    deleted = snapshot()

    assert absent == extreme == deleted


@requires_db
def test_moderator_queue_and_publication_ignore_telemetry(client):
    """The moderator queue card and the publication decision are identical
    across absent / extreme / deleted telemetry."""
    import uuid as _uuid

    from app.db.session import SessionLocal
    from tests.conftest import find_pending_queue_item

    _, author_token, _ = register_and_token(client)
    _, mod_token, _ = register_and_token(client)
    ah = _auth(author_token)
    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)
    reader_id, _reader_token, _ = register_and_token(client)

    pid = client.post("/api/v1/products", headers=ah, json={
        "name": f"QueueIso-{_uuid.uuid4().hex[:6]}", "category": "electronics",
    }).json()["id"]
    body = {"product_id": pid, "title": "Pending", "discussion": "Queued for review.",
            "verdict": "it_depends", "star_rating": 3}
    rid = client.post("/api/v1/reviews", headers=ah, json=body).json()["id"]

    def queue_card() -> dict:
        item = find_pending_queue_item(client, mh, rid)
        assert item is not None
        item.pop("suggested_sub_id", None)  # carries a random nonce
        return item

    absent = queue_card()
    assert absent["signals"]["duplicate_content"] is False

    db = SessionLocal()
    try:
        _flood_extreme_telemetry(db, _uuid.UUID(rid), 3, _uuid.UUID(reader_id))
    finally:
        db.close()
    extreme = queue_card()

    db = SessionLocal()
    try:
        _purge_telemetry(db, _uuid.UUID(rid))
    finally:
        db.close()
    deleted = queue_card()

    assert absent == extreme == deleted

    # Publication decision: two identical pending reviews, telemetry on one.
    def make_pending() -> str:
        return client.post("/api/v1/reviews", headers=ah, json={
            "product_id": pid, "title": "Pending", "discussion": "Queued for review.",
            "verdict": "it_depends", "star_rating": 3,
        }).json()["id"]

    clean_rid = make_pending()
    noisy_rid = make_pending()
    db = SessionLocal()
    try:
        _flood_extreme_telemetry(db, _uuid.UUID(noisy_rid), 3, _uuid.UUID(reader_id))
    finally:
        db.close()

    def publish(review_id: str) -> dict:
        resp = client.post(f"/api/v1/admin/reviews/{review_id}/publish", headers=mh)
        assert resp.status_code == 200, resp.text
        out = resp.json()
        return {k: out[k] for k in ("earn_eligible_status", "wilson_score",
                                    "helpful_votes", "unhelpful_votes")}

    assert publish(clean_rid) == publish(noisy_rid)


@requires_db
def test_honesty_fund_score_ignores_telemetry(client):
    """A review's Honesty Score — the only telemetry-independent input to its
    fund payout — is identical across absent / extreme / deleted telemetry."""
    import uuid as _uuid
    from datetime import date as _date

    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.commission import Commission
    from app.models.enums import CommissionTarget
    from app.models.honesty_fund import HonestyFundDistribution
    from app.services.earnings import split_commission
    from app.services.honesty_fund_service import distribute

    _, mod_token, _ = register_and_token(client, role="moderator")
    mh = _auth(mod_token)

    def free_cycle(used: set) -> _date:
        for year in range(1901, 2099):
            for month in range(1, 13):
                cycle = _date(year, month, 1)
                if cycle not in used:
                    used.add(cycle)
                    return cycle
        raise AssertionError("no free cycle_month")

    used_cycles: set = set()
    db = SessionLocal()
    try:
        used_cycles |= {r[0] for r in db.execute(
            select(HonestyFundDistribution.cycle_month).distinct())}
        used_cycles |= {r[0] for r in db.execute(
            select(Commission.cycle_month).distinct())}
    finally:
        db.close()

    def run_case(*, flood: bool, purge: bool) -> Decimal:
        _, author_token, _ = register_and_token(client)
        _, voter_token, _ = register_and_token(client)
        ah = _auth(author_token)
        voter_id = client.get("/api/v1/auth/me", headers=_auth(voter_token)).json()["id"]

        pid = client.post("/api/v1/products", headers=ah, json={
            "name": f"FundIso-{_uuid.uuid4().hex[:6]}", "category": "electronics",
        }).json()["id"]
        from tests.conftest import owned_photo_url
        rid = client.post("/api/v1/reviews", headers=ah, json={
            "product_id": pid, "title": "Disappointing", "price_paid": "100",
            "discussion": "Broke fast; honest warning about this product.",
            "verdict": "hard_pass", "star_rating": 2,
            "photo_url": owned_photo_url(ah),
        }).json()["id"]
        assert client.post(f"/api/v1/admin/reviews/{rid}/publish",
                           headers=mh).status_code == 200

        db = SessionLocal()
        try:
            from app.models.user import User
            voter = db.get(User, _uuid.UUID(voter_id))
            voter.trust_stage = 2
            voter.reputation_score = 100
            voter.created_at = datetime.now(UTC) - timedelta(days=60)
            db.commit()
        finally:
            db.close()
        assert client.post(f"/api/v1/reviews/{rid}/vote", headers=_auth(voter_token),
                           json={"vote": "up"}).status_code == 200

        if flood:
            db = SessionLocal()
            try:
                _flood_extreme_telemetry(db, _uuid.UUID(rid), 2, _uuid.UUID(voter_id))
            finally:
                db.close()
        if purge:
            db = SessionLocal()
            try:
                _purge_telemetry(db, _uuid.UUID(rid))
            finally:
                db.close()

        cycle = free_cycle(used_cycles)
        gross = (Decimal("30.00") / Decimal("0.30")).quantize(Decimal("0.01"))
        split = split_commission(gross)
        db = SessionLocal()
        try:
            db.add(Commission(
                commission_id=f"com_iso_{_uuid.uuid4().hex[:10]}",
                target_type=CommissionTarget.review, review_id=_uuid.UUID(rid),
                csv_source=f"iso:{_uuid.uuid4().hex[:12]}", row_reference="2",
                cycle_month=cycle, **split,
            ))
            db.commit()
            result = distribute(db, cycle_month=cycle)
            assert result["status"] == "distributed", result
            row = db.scalar(select(HonestyFundDistribution).where(
                HonestyFundDistribution.cycle_month == cycle,
                HonestyFundDistribution.review_id == _uuid.UUID(rid)))
            assert row is not None
            return Decimal(row.honesty_score)
        finally:
            db.close()

    absent = run_case(flood=False, purge=False)
    extreme = run_case(flood=True, purge=False)
    deleted = run_case(flood=True, purge=True)
    assert absent > 0
    assert absent == extreme == deleted


@requires_db
def test_internal_payout_eligibility_and_amount_ignore_telemetry(client):
    """Scheduled-payout eligibility and amount for a funded reviewer are
    identical across absent / extreme / deleted telemetry. No external provider
    is ever contacted — only ``schedule_payouts`` runs."""
    import uuid as _uuid
    from datetime import date as _date

    from sqlalchemy import select

    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.models.enums import PayoutStatus
    from app.models.honesty_fund import HonestyFundDistribution
    from app.models.payout import Payout
    from app.models.user import User

    fund_amount = (Decimal(settings.payout_min_php) + Decimal("25.00")).quantize(
        Decimal("0.01"))

    def run_case(*, flood: bool, purge: bool) -> tuple:
        uid, _token, _ = register_and_token(client)
        user_uuid = _uuid.UUID(uid)
        db = SessionLocal()
        try:
            user = db.get(User, user_uuid)
            user.payout_account = "payee@example.com"
            db.add(HonestyFundDistribution(
                distribution_id=f"hfd_iso_{_uuid.uuid4().hex[:8]}",
                cycle_month=_date(1970, 1, 1), review_id=None, reviewer_id=user.id,
                honesty_score=Decimal("1"), pool_amount=fund_amount,
                payout_amount=fund_amount))
            user.wallet_balance = fund_amount
            db.commit()
        finally:
            db.close()

        if flood:
            db = SessionLocal()
            try:
                # A published review so the FK on reader_ref/review_id holds.
                _, atok, _ = register_and_token(client)
                _, mtok, _ = register_and_token(client, role="moderator")
                rid, _ = make_published_review(client, _auth(atok), _auth(mtok),
                                               name=f"PayIso-{_uuid.uuid4().hex[:6]}")
                _flood_extreme_telemetry(db, _uuid.UUID(rid), 4, user_uuid)
            finally:
                db.close()
        if purge:
            db = SessionLocal()
            try:
                from app.models.telemetry import ReviewReadingSession
                db.execute(delete(ReviewReadingSession).where(
                    ReviewReadingSession.reader_ref == user_uuid))
                db.commit()
            finally:
                db.close()

        db = SessionLocal()
        try:
            from app.services import payout_service
            payout_service.schedule_payouts(db, when=_date(2026, 1, 15))
            row = db.scalar(select(Payout).where(Payout.user_id == user_uuid))
            assert row is not None
            return (str(row.amount), row.currency, row.status.value,
                    str(db.get(User, user_uuid).wallet_balance))
        finally:
            db.close()

    absent = run_case(flood=False, purge=False)
    extreme = run_case(flood=True, purge=False)
    deleted = run_case(flood=True, purge=True)
    assert absent[0] == str(fund_amount)
    assert absent[2] == PayoutStatus.scheduled.value
    assert absent == extreme == deleted
