"""SQLAlchemy models — the 15-table Data Dictionary.

Importing this package registers every model on `Base.metadata`, which Alembic's
env.py uses as the migration target.
"""

from app.models.comment import ReviewComment, ReviewCommentVote  # noqa: F401
from app.models.commission import Commission  # noqa: F401
from app.models.contract import ReviewContract  # noqa: F401
from app.models.honesty_fund import HonestyFundDistribution  # noqa: F401
from app.models.maintenance import CronCredential, CronRun  # noqa: F401
from app.models.membership import MembershipTierConfig  # noqa: F401
from app.models.moderation import ModerationLog  # noqa: F401
from app.models.otp import EmailOtp  # noqa: F401
from app.models.payout import Payout  # noqa: F401
from app.models.postback import AffiliatePostback  # noqa: F401
from app.models.product import PriceHistory, Product, ProductPlatform  # noqa: F401
from app.models.qa import Answer, Question  # noqa: F401
from app.models.request_board import RequestUpvote, ReviewRequest  # noqa: F401
from app.models.review import ReferralLink, Review, ReviewVersion  # noqa: F401
from app.models.session import Session  # noqa: F401
from app.models.token import TokenTransaction  # noqa: F401
from app.models.traffic import (  # noqa: F401
    RequestGeoBucket,
    ReviewViewBucket,
)
from app.models.user import Badge, User, UserBadge  # noqa: F401
from app.models.vote import EarnEligibleVote, ReviewVote  # noqa: F401

__all__ = [
    "User", "Badge", "UserBadge", "MembershipTierConfig",
    "Product", "ProductPlatform", "PriceHistory",
    "Review", "ReviewVersion", "ReferralLink", "Question", "Answer",
    "Session", "Commission", "HonestyFundDistribution",
    "ModerationLog", "EarnEligibleVote", "ReviewVote", "TokenTransaction",
    "ReviewRequest", "RequestUpvote", "ReviewContract", "Payout", "EmailOtp",
    "AffiliatePostback", "ReviewComment", "ReviewCommentVote",
]
