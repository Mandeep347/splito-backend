import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domain.user.models import User
from app.middleware.auth import get_current_user
from app.repositories.group_repository import GroupMemberRepository
from app.schemas.expense import (
    CreateExpenseRequest,
    ExpenseResponse,
    PaginatedExpenses,
    UpdateExpenseRequest,
)
from app.services.expense_service import ExpenseService
from app.services.notification_triggers import (
    notify_expense_created,
    notify_expense_reversed,
)

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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    svc: ExpenseService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    expense = await svc.create_expense(group_id, payload, current_user)

    # ── Fire-and-forget: notify group members ────────────────────────────────
    member_repo = GroupMemberRepository(db)
    members = await member_repo.get_active_members(group_id)
    member_ids = [m.user_id for m in members]

    background_tasks.add_task(
        notify_expense_created,
        group_id=group_id,
        expense_id=expense.id,
        paid_by_name=expense.paid_by_name,
        expense_title=expense.title,
        currency=expense.currency,
        amount=expense.total_amount,
        member_ids=member_ids,
        creator_id=current_user.id,
    )

    return expense


@router.get("/groups/{group_id}/expenses", response_model=PaginatedExpenses)
async def list_expenses(
    group_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=1000),
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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    svc: ExpenseService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    expense = await svc.reverse_expense(expense_id, current_user)

    # ── Fire-and-forget: notify group members ────────────────────────────────
    member_repo = GroupMemberRepository(db)
    members = await member_repo.get_active_members(expense.group_id)
    member_ids = [m.user_id for m in members]

    background_tasks.add_task(
        notify_expense_reversed,
        group_id=expense.group_id,
        expense_id=expense.id,
        expense_title=expense.title,
        member_ids=member_ids,
        reverser_id=current_user.id,
    )

    return expense
