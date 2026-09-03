"""Reading telemetry: model shape and privacy boundaries.

The constraint tests for this subsystem run against PostgreSQL in the later
collection task.  These fast model tests establish its public schema contract.
"""

from __future__ import annotations

from app.models.enums import ReaderKind
from app.models.telemetry import ReviewReadingSession


def test_reader_kind_has_exactly_two_members():
    assert {member.value for member in ReaderKind} == {"anon", "user"}


def test_the_model_declares_the_columns_the_service_writes():
    columns = set(ReviewReadingSession.__table__.columns.keys())
    assert {
        "impression_id",
        "review_id",
        "reader_kind",
        "reader_ref",
        "anon_ref",
        "started_at",
        "last_seen_at",
        "active_ms",
        "body_active_ms",
        "wall_ms",
        "scroll_milestone",
        "checkpoints",
        "max_seq",
        "clamped",
        "vote_client_after_ms",
        "report_client_after_ms",
        "comment_client_after_ms",
        "share_client_after_ms",
        "photo_client_after_ms",
        "outlink_client_after_ms",
        "first_vote_at",
        "active_ms_at_first_vote",
        "country",
        "word_count_at_view",
        "star_rating_at_view",
        "device_class",
    } <= columns


def test_no_user_agent_column_exists():
    """The raw User-Agent is never persisted — only the derived bucket."""
    columns = set(ReviewReadingSession.__table__.columns.keys())
    assert "user_agent" not in columns
    assert "device_class" in columns
