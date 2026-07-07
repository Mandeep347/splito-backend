"""
Notification trigger functions — called as FastAPI BackgroundTasks.

Rules:
  - NEVER raise exceptions to the caller.
  - If notification insert fails, log and return silently.
  - Each trigger gets its own DB session (background tasks run
    after the response is sent, so the request session is closed).
  - One session per trigger call, committed independently.
"""
import logging
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.repositories.notification_repository import NotificationRepository

logger = logging.getLogger(__name__)


# ─── Internal helper ─────────────────────────────────────────────────────────

async def _notify(
    user_ids: list[uuid.UUID],
    type: str,
    title: str,
    message: str,
    metadata: dict | None = None,
) -> None:
    """
    Opens a fresh DB session, inserts one notification per user_id,
    commits, and closes. Swallows all exceptions.
    """
    if not user_ids:
        return
    try:
        async with AsyncSessionLocal() as session:
            repo = NotificationRepository(session)
            for uid in user_ids:
                await repo.create_notification(
                    user_id=uid,
                    type=type,
                    title=title,
                    message=message,
                    metadata=metadata,
                )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to create notifications type=%s users=%s: %s",
            type, user_ids, exc, exc_info=True,
        )


# ─── Trigger 1 — Expense created ─────────────────────────────────────────────

async def notify_expense_created(
    group_id: uuid.UUID,
    expense_id: uuid.UUID,
    paid_by_name: str,
    expense_title: str,
    currency: str,
    amount: Decimal,
    member_ids: list[uuid.UUID],   # all active group member user IDs
    creator_id: uuid.UUID,          # excluded from notification
) -> None:
    recipients = [uid for uid in member_ids if uid != creator_id]
    if not recipients:
        return
    await _notify(
        user_ids=recipients,
        type="EXPENSE_CREATED",
        title="New expense added",
        message=f'{paid_by_name} added "{expense_title}" — {currency}{amount}',
        metadata={
            "group_id": str(group_id),
            "expense_id": str(expense_id),
            "amount": str(amount),
        },
    )


# ─── Trigger 2 — Expense reversed ────────────────────────────────────────────

async def notify_expense_reversed(
    group_id: uuid.UUID,
    expense_id: uuid.UUID,
    expense_title: str,
    member_ids: list[uuid.UUID],
    reverser_id: uuid.UUID,         # excluded from notification
) -> None:
    recipients = [uid for uid in member_ids if uid != reverser_id]
    if not recipients:
        return
    await _notify(
        user_ids=recipients,
        type="EXPENSE_REVERSED",
        title="Expense reversed",
        message=f'"{expense_title}" was reversed',
        metadata={
            "group_id": str(group_id),
            "expense_id": str(expense_id),
        },
    )


# ─── Trigger 3 — Settlement recorded ─────────────────────────────────────────

async def notify_settlement_recorded(
    group_id: uuid.UUID,
    settlement_id: uuid.UUID,
    from_user_name: str,
    to_user_id: uuid.UUID,
    currency: str,
    amount: Decimal,
) -> None:
    await _notify(
        user_ids=[to_user_id],
        type="SETTLEMENT_RECORDED",
        title="Payment received",
        message=f"{from_user_name} paid you {currency}{amount}",
        metadata={
            "group_id": str(group_id),
            "settlement_id": str(settlement_id),
            "amount": str(amount),
        },
    )


# ─── Trigger 4 — Member added ─────────────────────────────────────────────────

async def notify_member_added(
    group_id: uuid.UUID,
    group_name: str,
    new_member_id: uuid.UUID,
) -> None:
    await _notify(
        user_ids=[new_member_id],
        type="MEMBER_ADDED",
        title="Added to group",
        message=f'You were added to "{group_name}"',
        metadata={
            "group_id": str(group_id),
        },
    )
