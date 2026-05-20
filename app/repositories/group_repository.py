import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.group.models import Group, GroupMember, GroupStatus, MemberStatus
from app.domain.user.models import User
from app.repositories.base import BaseRepository


class GroupRepository(BaseRepository[Group]):
    model = Group

    async def get_by_id_with_members(self, group_id: uuid.UUID) -> Group | None:
        result = await self.db.scalar(
            select(Group)
            .where(Group.id == group_id)
            .options(selectinload(Group.members).selectinload(GroupMember.user))
        )
        return result

    async def get_user_groups(self, user_id: uuid.UUID) -> list[Group]:
        """All active groups a user belongs to."""
        result = await self.db.scalars(
            select(Group)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(
                GroupMember.user_id == user_id,
                GroupMember.status == MemberStatus.ACTIVE,
                Group.status == GroupStatus.ACTIVE,
            )
            .options(selectinload(Group.members))
        )
        return list(result.all())


class GroupMemberRepository(BaseRepository[GroupMember]):
    model = GroupMember

    async def get_membership(
        self, group_id: uuid.UUID, user_id: uuid.UUID
    ) -> GroupMember | None:
        return await self.db.scalar(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
            )
        )

    async def get_active_membership(
        self, group_id: uuid.UUID, user_id: uuid.UUID
    ) -> GroupMember | None:
        return await self.db.scalar(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
                GroupMember.status == MemberStatus.ACTIVE,
            )
        )

    async def get_active_members(self, group_id: uuid.UUID) -> list[GroupMember]:
        result = await self.db.scalars(
            select(GroupMember)
            .where(
                GroupMember.group_id == group_id,
                GroupMember.status == MemberStatus.ACTIVE,
            )
            .options(selectinload(GroupMember.user))
        )
        return list(result.all())
