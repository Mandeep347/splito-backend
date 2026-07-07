import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.notification.models import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def get_user_notifications(self, user_id: uuid.UUID) -> list[Notification]:
        """All notifications for a user, newest first."""
        result = await self.db.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
        )
        return list(result.all())

    async def get_by_id_for_user(
        self, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> Notification | None:
        """Fetch a single notification only if it belongs to the given user."""
        return await self.db.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )

    async def mark_one_read(
        self, notification_id: uuid.UUID, user_id: uuid.UUID
    ) -> Notification | None:
        """Mark a single notification as read. Returns updated row or None."""
        notification = await self.get_by_id_for_user(notification_id, user_id)
        if not notification:
            return None
        notification.is_read = True
        await self.db.flush()
        return notification

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        """
        Single UPDATE statement — marks every unread notification for this
        user as read.  Returns the number of rows updated.
        """
        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .values(is_read=True)
        )
        await self.db.flush()
        return result.rowcount

    async def create_notification(
        self,
        user_id: uuid.UUID,
        type: str,
        title: str,
        message: str,
        metadata: dict | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            is_read=False,
            metadata_=metadata,
        )
        self.db.add(notification)
        await self.db.flush()
        return notification
