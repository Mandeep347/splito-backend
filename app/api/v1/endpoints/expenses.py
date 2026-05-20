import uuid

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domain.user.models import User
from app.middleware.auth import get_current_user
from app.schemas.expense import (
    CreateExpenseRequest,
    ExpenseResponse,
    PaginatedExpenses,
    UpdateExpenseRequest,
)
from app.services.expense_service import ExpenseService

router = APIRouter(tags=["Expenses"])


def _svc(db: AsyncSession = Depends(get_db)) -> ExpenseService:
    return ExpenseService(db)


@router.post(
    "/groups/{group_id}/expenses",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_expense(
    group_id: uuid.UUID,
    payload: CreateExpenseRequest,
    current_user: User = Depends(get_current_user),
    svc: ExpenseService = Depends(_svc),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    # Idempotency-Key is logged/stored at infra layer; service layer is idempotent by design
    return await svc.create_expense(group_id, payload, current_user)


@router.get("/groups/{group_id}/expenses", response_model=PaginatedExpenses)
async def list_expenses(
    group_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    svc: ExpenseService = Depends(_svc),
):
    return await svc.get_group_expenses(group_id, current_user, page, limit)


@router.get("/expenses/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: ExpenseService = Depends(_svc),
):
    return await svc.get_expense(expense_id, current_user)


@router.patch("/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: uuid.UUID,
    payload: UpdateExpenseRequest,
    current_user: User = Depends(get_current_user),
    svc: ExpenseService = Depends(_svc),
):
    return await svc.update_expense(expense_id, payload, current_user)


@router.patch("/expenses/{expense_id}/reverse", response_model=ExpenseResponse)
async def reverse_expense(
    expense_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: ExpenseService = Depends(_svc),
):
    return await svc.reverse_expense(expense_id, current_user)
