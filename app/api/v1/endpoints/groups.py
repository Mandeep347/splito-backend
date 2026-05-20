import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domain.user.models import User
from app.middleware.auth import get_current_user
from app.schemas.group import (
    AddMemberRequest,
    CreateGroupRequest,
    GroupDetailResponse,
    GroupMemberResponse,
    GroupResponse,
    UpdateGroupRequest,
)
from app.services.group_service import GroupService

router = APIRouter(prefix="/groups", tags=["Groups"])


def _svc(db: AsyncSession = Depends(get_db)) -> GroupService:
    return GroupService(db)


@router.post("", response_model=GroupDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: CreateGroupRequest,
    current_user: User = Depends(get_current_user),
    svc: GroupService = Depends(_svc),
):
    return await svc.create_group(payload, current_user)


@router.get("", response_model=list[GroupResponse])
async def list_groups(
    current_user: User = Depends(get_current_user),
    svc: GroupService = Depends(_svc),
):
    return await svc.get_user_groups(current_user)


@router.get("/{group_id}", response_model=GroupDetailResponse)
async def get_group(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: GroupService = Depends(_svc),
):
    return await svc.get_group_detail(group_id, current_user)


@router.patch("/{group_id}", response_model=GroupDetailResponse)
async def update_group(
    group_id: uuid.UUID,
    payload: UpdateGroupRequest,
    current_user: User = Depends(get_current_user),
    svc: GroupService = Depends(_svc),
):
    return await svc.update_group(group_id, payload, current_user)


@router.patch("/{group_id}/archive", response_model=GroupDetailResponse)
async def archive_group(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: GroupService = Depends(_svc),
):
    return await svc.archive_group(group_id, current_user)


# ── Member sub-routes ─────────────────────────────────────────────────────────

@router.get("/{group_id}/members", response_model=list[GroupMemberResponse])
async def get_members(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: GroupService = Depends(_svc),
):
    return await svc.get_members(group_id, current_user)


@router.post(
    "/{group_id}/members",
    response_model=GroupMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    group_id: uuid.UUID,
    payload: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    svc: GroupService = Depends(_svc),
):
    return await svc.add_member(group_id, payload, current_user)


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: GroupService = Depends(_svc),
):
    await svc.remove_member(group_id, user_id, current_user)
