import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domain.user.models import User
from app.middleware.auth import get_current_user
from app.repositories.balance_repository import BalanceCacheRepository
from app.repositories.group_repository import GroupMemberRepository
from app.schemas.balance import (
    CreateSettlementRequest,
    GroupBalancesResponse,
    PairwiseBalance,
    SettlementResponse,
    SimplifiedBalance,
    SimplifiedBalancesResponse,
    UserOverallBalance,
)
from app.services.balance_service import BalanceService
from app.services.settlement_service import SettlementService

router = APIRouter(tags=["Balances & Settlements"])


def _balance_svc(db: AsyncSession = Depends(get_db)) -> BalanceService:
    return BalanceService(db)


def _settlement_svc(db: AsyncSession = Depends(get_db)) -> SettlementService:
    return SettlementService(db)


# ── Balances ──────────────────────────────────────────────────────────────────

@router.get("/groups/{group_id}/balances", response_model=GroupBalancesResponse)
async def get_group_balances(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    svc: BalanceService = Depends(_balance_svc),
):
    member_repo = GroupMemberRepository(db)
    from app.core.exceptions import UserNotInGroupError
    if not await member_repo.get_active_membership(group_id, current_user.id):
        raise UserNotInGroupError("You are not a member of this group.")

    from app.domain.group.models import Group
    group = await db.scalar(select(Group).where(Group.id == group_id))
    currency = group.default_currency if group else "INR"

    balances = await svc.get_group_balances(group_id)

    pairs = []
    for b in balances:
        from_user = await db.scalar(select(User).where(User.id == b.user_id))
        to_user = await db.scalar(select(User).where(User.id == b.other_user_id))
        pairs.append(PairwiseBalance(
            from_user_id=b.user_id,
            from_user_name=from_user.name if from_user else "Unknown",
            to_user_id=b.other_user_id,
            to_user_name=to_user.name if to_user else "Unknown",
            amount=Decimal(str(b.balance_amount)),
            currency=currency,
        ))

    return GroupBalancesResponse(group_id=group_id, currency=currency, balances=pairs)


@router.get("/groups/{group_id}/balances/simplified", response_model=SimplifiedBalancesResponse)
async def get_simplified_balances(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    svc: BalanceService = Depends(_balance_svc),
):
    member_repo = GroupMemberRepository(db)
    from app.core.exceptions import UserNotInGroupError
    if not await member_repo.get_active_membership(group_id, current_user.id):
        raise UserNotInGroupError("You are not a member of this group.")

    from app.domain.group.models import Group
    group = await db.scalar(select(Group).where(Group.id == group_id))
    currency = group.default_currency if group else "INR"

    simplified = await svc.simplify(group_id)

    transactions = []
    for debtor_id, creditor_id, amount in simplified:
        debtor = await db.scalar(select(User).where(User.id == debtor_id))
        creditor = await db.scalar(select(User).where(User.id == creditor_id))
        transactions.append(SimplifiedBalance(
            from_user_id=debtor_id,
            from_user_name=debtor.name if debtor else "Unknown",
            to_user_id=creditor_id,
            to_user_name=creditor.name if creditor else "Unknown",
            amount=amount,
            currency=currency,
        ))

    return SimplifiedBalancesResponse(
        group_id=group_id, currency=currency, transactions=transactions
    )


@router.get("/users/me/balances", response_model=list[UserOverallBalance])
async def get_my_overall_balances(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    svc: BalanceService = Depends(_balance_svc),
):
    """Net cross-group balance summary for the logged-in user."""
    rows = await svc.get_user_all_group_balances(current_user.id)

    # Aggregate by counterpart across groups
    net: dict[uuid.UUID, Decimal] = {}
    for row in rows:
        oid = row.other_user_id
        net[oid] = net.get(oid, Decimal("0")) + Decimal(str(row.balance_amount))

    result = []
    for other_id, amount in net.items():
        if abs(amount) < Decimal("0.005"):
            continue
        other = await db.scalar(select(User).where(User.id == other_id))
        result.append(UserOverallBalance(
            counterpart_user_id=other_id,
            counterpart_name=other.name if other else "Unknown",
            net_amount=amount,
            currency="INR",  # multi-currency aggregation is an advanced feature
        ))
    return result


# ── Settlements ───────────────────────────────────────────────────────────────

@router.post(
    "/groups/{group_id}/settlements",
    response_model=SettlementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_settlement(
    group_id: uuid.UUID,
    payload: CreateSettlementRequest,
    current_user: User = Depends(get_current_user),
    svc: SettlementService = Depends(_settlement_svc),
):
    return await svc.create_settlement(group_id, payload, current_user)


@router.get("/groups/{group_id}/settlements", response_model=list[SettlementResponse])
async def list_settlements(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: SettlementService = Depends(_settlement_svc),
):
    return await svc.get_group_settlements(group_id, current_user)
