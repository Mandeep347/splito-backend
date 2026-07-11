import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domain.user.models import User
from app.middleware.auth import get_current_user
from app.schemas.analytics import GroupAnalyticsResponse, UserAnalyticsResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(tags=["Analytics"])


def _svc(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db)


@router.get(
    "/groups/{group_id}/analytics",
    response_model=GroupAnalyticsResponse,
    summary="Get group analytics",
    description=(
        "Returns comprehensive analytics for a group: "
        "total spending, per-member breakdown, settlement rate, "
        "largest expense, top spender, and monthly trend (last 12 months). "
        "Requester must be an active group member."
    ),
)
async def get_group_analytics(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: AnalyticsService = Depends(_svc),
) -> GroupAnalyticsResponse:
    return await svc.get_group_analytics(group_id, current_user.id)


@router.get(
    "/users/me/analytics",
    response_model=UserAnalyticsResponse,
    summary="Get my analytics",
    description=(
        "Returns cross-group analytics for the logged-in user: "
        "total paid, net balance, per-group breakdown, "
        "most expensive group, and monthly spending trend (last 12 months)."
    ),
)
async def get_user_analytics(
    current_user: User = Depends(get_current_user),
    svc: AnalyticsService = Depends(_svc),
) -> UserAnalyticsResponse:
    return await svc.get_user_analytics(current_user.id)
