from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    ExpenseNotFoundError,
    GroupNotFoundError,
    InvalidCredentialsError,
    InvalidSplitPercentageError,
    InvalidSplitTotalError,
    OutstandingBalanceError,
    SelfSettlementError,
    SettlementExceedsBalanceError,
    SettlementNotFoundError,
    SplitoDomainError,
    TokenExpiredError,
    UnauthorizedError,
    UserAlreadyExistsError,
    UserAlreadyInGroupError,
    UserNotFoundError,
    UserNotInGroupError,
)
from app.schemas.common import ErrorResponse


def _error(request: Request, status: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(
        status=status,
        error=code,
        message=message,
        path=str(request.url.path),
    )
    return JSONResponse(status_code=status, content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(UserAlreadyExistsError)
    async def _(req: Request, exc: UserAlreadyExistsError):
        return _error(req, 409, "USER_ALREADY_EXISTS", str(exc))

    @app.exception_handler(UserNotFoundError)
    async def _(req: Request, exc: UserNotFoundError):
        return _error(req, 404, "USER_NOT_FOUND", str(exc))

    @app.exception_handler(InvalidCredentialsError)
    async def _(req: Request, exc: InvalidCredentialsError):
        return _error(req, 401, "INVALID_CREDENTIALS", str(exc))

    @app.exception_handler(TokenExpiredError)
    async def _(req: Request, exc: TokenExpiredError):
        return _error(req, 401, "TOKEN_EXPIRED", str(exc))

    @app.exception_handler(UnauthorizedError)
    async def _(req: Request, exc: UnauthorizedError):
        return _error(req, 403, "FORBIDDEN", str(exc))

    @app.exception_handler(GroupNotFoundError)
    async def _(req: Request, exc: GroupNotFoundError):
        return _error(req, 404, "GROUP_NOT_FOUND", str(exc))

    @app.exception_handler(UserNotInGroupError)
    async def _(req: Request, exc: UserNotInGroupError):
        return _error(req, 422, "USER_NOT_IN_GROUP", str(exc))

    @app.exception_handler(UserAlreadyInGroupError)
    async def _(req: Request, exc: UserAlreadyInGroupError):
        return _error(req, 409, "USER_ALREADY_IN_GROUP", str(exc))

    @app.exception_handler(OutstandingBalanceError)
    async def _(req: Request, exc: OutstandingBalanceError):
        return _error(req, 422, "OUTSTANDING_BALANCE_EXISTS", str(exc))

    @app.exception_handler(InvalidSplitTotalError)
    async def _(req: Request, exc: InvalidSplitTotalError):
        return _error(req, 422, "INVALID_SPLIT_TOTAL", str(exc))

    @app.exception_handler(SelfSettlementError)
    async def _(req: Request, exc: SelfSettlementError):
        return _error(req, 422, "SELF_SETTLEMENT_INVALID", str(exc))

    @app.exception_handler(SettlementExceedsBalanceError)
    async def _(req: Request, exc: SettlementExceedsBalanceError):
        return _error(req, 422, "SETTLEMENT_EXCEEDS_BALANCE", str(exc))

    @app.exception_handler(ExpenseNotFoundError)
    async def _(req: Request, exc: ExpenseNotFoundError):
        return _error(req, 404, "EXPENSE_NOT_FOUND", str(exc))

    @app.exception_handler(SettlementNotFoundError)
    async def _(req: Request, exc: SettlementNotFoundError):
        return _error(req, 404, "SETTLEMENT_NOT_FOUND", str(exc))

    @app.exception_handler(InvalidSplitPercentageError)
    async def _(req: Request, exc: InvalidSplitPercentageError):
        return _error(req, 422, "INVALID_SPLIT_PERCENTAGE", str(exc))

    @app.exception_handler(SplitoDomainError)
    async def _(req: Request, exc: SplitoDomainError):
        # Catch-all for any unhandled domain error
        return _error(req, 422, "DOMAIN_ERROR", str(exc))
