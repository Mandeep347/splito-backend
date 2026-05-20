import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    GroupNotFoundError,
    OutstandingBalanceError,
    UnauthorizedError,
    UserAlreadyInGroupError,
    UserNotFoundError,
    UserNotInGroupError,
)
from app.domain.group.models import (
    Group,
    GroupMember,
    GroupStatus,
    MemberRole,
    MemberStatus,
)
from app.domain.user.models import User
from app.repositories.group_repository import GroupMemberRepository, GroupRepository
from app.schemas.group import (
    AddMemberRequest,
    CreateGroupRequest,
    GroupDetailResponse,
    GroupMemberResponse,
    GroupResponse,
    UpdateGroupRequest,
)
from app.services.balance_service import BalanceService


def _to_group_response(group: Group) -> GroupResponse:
    active = [m for m in group.members if m.status == MemberStatus.ACTIVE]
    return GroupResponse(
        id=group.id,
        name=group.name,
        default_currency=group.default_currency,
        status=group.status,
        created_by=group.created_by,
        created_at=group.created_at,
        members_count=len(active),
    )


def _to_member_response(member: GroupMember) -> GroupMemberResponse:
    return GroupMemberResponse(
        user_id=member.user_id,
        name=member.user.name,
        email=member.user.email,
        role=member.role,
        status=member.status,
        joined_at=member.joined_at,
    )


def _to_detail_response(group: Group) -> GroupDetailResponse:
    active = [m for m in group.members if m.status == MemberStatus.ACTIVE]
    return GroupDetailResponse(
        id=group.id,
        name=group.name,
        default_currency=group.default_currency,
        status=group.status,
        created_by=group.created_by,
        created_at=group.created_at,
        members_count=len(active),
        members=[_to_member_response(m) for m in active],
    )


class GroupService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.group_repo = GroupRepository(db)
        self.member_repo = GroupMemberRepository(db)
        self.balance_svc = BalanceService(db)

    # ── Group CRUD ────────────────────────────────────────────────────────────

    async def create_group(
        self, payload: CreateGroupRequest, creator: User
    ) -> GroupDetailResponse:
        group = Group(
            name=payload.name,
            default_currency=payload.default_currency.upper(),
            created_by=creator.id,
        )
        self.db.add(group)
        await self.db.flush()

        # Creator is automatically an ADMIN member
        member = GroupMember(
            group_id=group.id,
            user_id=creator.id,
            role=MemberRole.ADMIN,
            status=MemberStatus.ACTIVE,
        )
        self.db.add(member)
        await self.db.flush()

        group = await self.group_repo.get_by_id_with_members(group.id)
        return _to_detail_response(group)  # type: ignore

    async def get_user_groups(self, user: User) -> list[GroupResponse]:
        groups = await self.group_repo.get_user_groups(user.id)
        return [_to_group_response(g) for g in groups]

    async def get_group_detail(
        self, group_id: uuid.UUID, user: User
    ) -> GroupDetailResponse:
        group = await self._require_active_member(group_id, user.id)
        return _to_detail_response(group)

    async def update_group(
        self, group_id: uuid.UUID, payload: UpdateGroupRequest, user: User
    ) -> GroupDetailResponse:
        group = await self._require_admin(group_id, user.id)
        if payload.name is not None:
            group.name = payload.name
        await self.db.flush()
        group = await self.group_repo.get_by_id_with_members(group.id)
        return _to_detail_response(group)  # type: ignore

    async def archive_group(self, group_id: uuid.UUID, user: User) -> GroupDetailResponse:
        group = await self._require_admin(group_id, user.id)
        group.status = GroupStatus.ARCHIVED
        await self.db.flush()
        group = await self.group_repo.get_by_id_with_members(group.id)
        return _to_detail_response(group)  # type: ignore

    # ── Member management ─────────────────────────────────────────────────────

    async def add_member(
        self, group_id: uuid.UUID, payload: AddMemberRequest, requester: User
    ) -> GroupMemberResponse:
        await self._require_active_member(group_id, requester.id)

        target = await self.db.scalar(
            select(User).where(User.email == payload.email, User.is_active == True)
        )
        if not target:
            raise UserNotFoundError(f"No active user with email {payload.email!r}.")

        existing = await self.member_repo.get_membership(group_id, target.id)
        if existing:
            if existing.status == MemberStatus.ACTIVE:
                raise UserAlreadyInGroupError("User is already an active member of this group.")
            # Re-activate previously removed/left member
            existing.status = MemberStatus.ACTIVE
            existing.role = MemberRole.MEMBER
            await self.db.flush()
            return _to_member_response(existing)

        member = GroupMember(
            group_id=group_id,
            user_id=target.id,
            role=MemberRole.MEMBER,
            status=MemberStatus.ACTIVE,
        )
        self.db.add(member)
        await self.db.flush()

        # Re-load with user relationship
        member = await self.member_repo.get_active_membership(group_id, target.id)
        return _to_member_response(member)  # type: ignore

    async def remove_member(
        self, group_id: uuid.UUID, target_user_id: uuid.UUID, requester: User
    ) -> None:
        await self._require_admin(group_id, requester.id)

        membership = await self.member_repo.get_active_membership(group_id, target_user_id)
        if not membership:
            raise UserNotInGroupError("User is not an active member of this group.")

        # Business Rule: cannot remove member with pending balance
        net = await self.balance_svc.get_user_net_balance(group_id, target_user_id)
        if abs(net) > 0:
            raise OutstandingBalanceError(
                "Cannot remove member with an outstanding balance. Settle debts first."
            )

        membership.status = MemberStatus.REMOVED
        await self.db.flush()

    async def get_members(
        self, group_id: uuid.UUID, user: User
    ) -> list[GroupMemberResponse]:
        await self._require_active_member(group_id, user.id)
        members = await self.member_repo.get_active_members(group_id)
        return [_to_member_response(m) for m in members]

    # ── Guards ────────────────────────────────────────────────────────────────

    async def _require_active_member(self, group_id: uuid.UUID, user_id: uuid.UUID) -> Group:
        group = await self.group_repo.get_by_id_with_members(group_id)
        if not group or group.status == GroupStatus.ARCHIVED:
            raise GroupNotFoundError(f"Group {group_id} not found or archived.")
        membership = await self.member_repo.get_active_membership(group_id, user_id)
        if not membership:
            raise UserNotInGroupError("You are not a member of this group.")
        return group

    async def _require_admin(self, group_id: uuid.UUID, user_id: uuid.UUID) -> Group:
        group = await self._require_active_member(group_id, user_id)
        membership = await self.member_repo.get_active_membership(group_id, user_id)
        if not membership or membership.role != MemberRole.ADMIN:
            raise UnauthorizedError("Only group admins can perform this action.")
        return group
