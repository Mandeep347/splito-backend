import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserNotFoundError
from app.domain.notification.models import Notification
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import NotificationResponse, ReadAllResponse


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = NotificationRepository(db)

    async def get_notifications(self, user_id: uuid.UUID) -> list[NotificationResponse]:
        notifications = await self.repo.get_user_notifications(user_id)
        return [NotificationResponse.from_orm_model(n) for n in notifications]

    async def mark_one_read(
        self, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> NotificationResponse:
        notification = await self.repo.mark_one_read(notification_id, user_id)
        if not notification:
            from app.core.exceptions import NotificationNotFoundError
            raise NotificationNotFoundError(
                f"Notification {notification_id} not found."
            )
        return NotificationResponse.from_orm_model(notification)

    async def mark_all_read(self, user_id: uuid.UUID) -> ReadAllResponse:
        count = await self.repo.mark_all_read(user_id)
        return ReadAllResponse(updated_count=count)
