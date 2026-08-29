"""The internal staff reference never enters a public response schema."""

from app.api.v1.routes.admin_console import ReviewerRow
from app.schemas.auth import UserOut
from app.schemas.comment import CommentOut
from app.schemas.qa import AnswerOut, QuestionOut
from app.schemas.review import FeedAuthor, FeedItemOut, ReviewOut
from app.schemas.user import UserTrustOut


def test_public_user_schemas_do_not_declare_staff_reference():
    public = (
        UserOut,
        UserTrustOut,
        FeedAuthor,
        FeedItemOut,
        ReviewOut,
        QuestionOut,
        AnswerOut,
        CommentOut,
        ReviewerRow,
    )
    for schema in public:
        assert "staff_ref" not in schema.model_fields, schema.__name__
        assert "is_super_admin" not in schema.model_fields, schema.__name__


def test_new_user_columns_are_deferred_during_code_before_migration_window():
    from app.models.user import User

    assert User.staff_ref.property.deferred
    assert User.is_super_admin.property.deferred
