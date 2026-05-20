"""
Domain-specific exceptions.
These map cleanly to HTTP error codes in the exception handlers.
"""


class SplitoDomainError(Exception):
    """Base class for all domain errors."""


# ─── Auth ────────────────────────────────────────────────────────────────────

class InvalidCredentialsError(SplitoDomainError):
    pass


class TokenExpiredError(SplitoDomainError):
    pass


class UnauthorizedError(SplitoDomainError):
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
    """Raised when trying to remove a member who still has a pending balance."""
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
