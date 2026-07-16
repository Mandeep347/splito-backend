"""
Import all SQLAlchemy models in dependency order so the mapper
can resolve string-based relationship references.

Import this module anywhere you need the full model registry,
e.g. Alembic env.py and the test conftest.
"""
from app.domain.user.models import User                             # noqa: F401
from app.domain.group.models import Group, GroupMember              # noqa: F401
from app.domain.expense.models import Expense, ExpenseParticipant   # noqa: F401
from app.domain.settlement.models import Settlement                 # noqa: F401
from app.domain.balance.models import LedgerEntry, BalanceCache     # noqa: F401
from app.domain.notification.models import Notification             # noqa: F401
from app.domain.token.models import UserToken                       # noqa: F401
