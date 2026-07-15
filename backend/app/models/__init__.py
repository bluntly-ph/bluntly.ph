"""SQLAlchemy models — the 15-table Data Dictionary.

Importing this package registers every model on `Base.metadata`, which Alembic's
env.py uses as the migration target.
"""

from app.models.commission import Commission  # noqa: F401
from app.models.honesty_fund import HonestyFundDistribution  # noqa: F401
from app.models.membership import MembershipTierConfig  # noqa: F401
from app.models.moderation import ModerationLog  # noqa: F401
from app.models.product import PriceHistory, Product, ProductPlatform  # noqa: F401
from app.models.qa import Answer, Question  # noqa: F401
from app.models.review import ReferralLink, Review, ReviewVersion  # noqa: F401
from app.models.seller_review import SellerReview  # noqa: F401
from app.models.session import Session  # noqa: F401
from app.models.token import TokenTransaction  # noqa: F401
from app.models.user import Badge, User, UserBadge  # noqa: F401
from app.models.vote import EarnEligibleVote, ReviewVote  # noqa: F401

__all__ = [
    "User", "Badge", "UserBadge", "MembershipTierConfig",
    "Product", "ProductPlatform", "PriceHistory",
    "Review", "ReviewVersion", "ReferralLink", "Question", "Answer", "SellerReview",
    "Session", "Commission", "HonestyFundDistribution",
    "ModerationLog", "EarnEligibleVote", "ReviewVote", "TokenTransaction",
]
