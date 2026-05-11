"""SQLAlchemy ORM models. Importing this package registers every model on `Base`."""

# WHY: Alembic's env.py imports `Base` and expects every model to be loaded so
# `Base.metadata` knows about each table. Re-exporting here is the canonical
# way to ensure that without scattering `from app.models.x import X` lines.
from app.models.base import Base
from app.models.category import Category
from app.models.conversation import Conversation
from app.models.insight import ProactiveInsight
from app.models.memory import AgentMemory
from app.models.message import Message
from app.models.subscription import Subscription
from app.models.transaction import Transaction
from app.models.user import User

__all__ = [
    "AgentMemory",
    "Base",
    "Category",
    "Conversation",
    "Message",
    "ProactiveInsight",
    "Subscription",
    "Transaction",
    "User",
]
