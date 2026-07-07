import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SplitoDomainError
from app.db.session import get_db
from app.domain.user.models import User
from app.middleware.auth import get_current_user
from app.schemas.notification import NotificationResponse, ReadAllResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _svc(db: AsyncSession = Depends(get_db)) -> NotificationService:
    return NotificationService(db)


@router.get("", response_model=list[NotificationResponse])
async def get_notifications(
    current_user: User = Depends(get_current_user),
    svc: NotificationService = Depends(_svc),
):
    """Returns all notifications for the logged-in user, newest first."""
    return await svc.get_notifications(current_user.id)


@router.patch("/read-all", response_model=ReadAllResponse)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    svc: NotificationService = Depends(_svc),
):
    """
    Marks ALL unread notifications for the logged-in user as read
    in a single UPDATE query.
    """
    return await svc.mark_all_read(current_user.id)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: NotificationService = Depends(_svc),
):
    """
    Marks a single notification as read.
    Returns 404 if notification doesn't exist or belongs to a different user.
    """
    return await svc.mark_one_read(notification_id, current_user.id)
