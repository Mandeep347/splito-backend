"""Domain-specific exceptions mapped to HTTP codes in exception_handlers.py."""


class SplitoDomainError(Exception):
    """Base class for all domain errors."""


# ─── Auth ────────────────────────────────────────────────────────────────────

class InvalidCredentialsError(SplitoDomainError):
    pass

class TokenExpiredError(SplitoDomainError):
    pass

class UnauthorizedError(SplitoDomainError):
    pass

class EmailNotVerifiedError(SplitoDomainError):
    pass

class InvalidTokenError(SplitoDomainError):
    pass


# ─── User ────────────────────────────────────────────────────────────────────

class UserNotFoundError(SplitoDomainError):
    pass

class UserAlreadyExistsError(SplitoDomainError):
    pass


# ─── Group ───────────────────────────────────────────────────────────────────

class GroupNotFoundError(SplitoDomainError):
    pass

class UserNotInGroupError(SplitoDomainError):
    pass

class UserAlreadyInGroupError(SplitoDomainError):
    pass

class OutstandingBalanceError(SplitoDomainError):
    pass


# ─── Expense ─────────────────────────────────────────────────────────────────

class ExpenseNotFoundError(SplitoDomainError):
    pass

class InvalidSplitTotalError(SplitoDomainError):
    pass

class InvalidSplitPercentageError(SplitoDomainError):
    pass


# ─── Settlement ──────────────────────────────────────────────────────────────

class SettlementNotFoundError(SplitoDomainError):
    pass

class SelfSettlementError(SplitoDomainError):
    pass

class SettlementExceedsBalanceError(SplitoDomainError):
    pass


# ─── Notification ─────────────────────────────────────────────────────────────

class NotificationNotFoundError(SplitoDomainError):
    pass
