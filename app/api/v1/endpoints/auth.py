from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domain.user.models import User
from app.middleware.auth import get_current_user
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateUserRequest,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()


# ─── Auth endpoints ──────────────────────────────────────────────────────────

@router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user, _ = await service.register(payload)
    return user


@router.post("/auth/login", response_model=TokenResponse, summary="Login and get tokens")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    return await service.login(payload)


@router.post("/auth/refresh", response_model=TokenResponse, summary="Refresh access token")
async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    return await service.refresh(payload.refresh_token)


# ─── User endpoints ──────────────────────────────────────────────────────────

@router.get("/users/me", response_model=UserResponse, summary="Get current user")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/users/me", response_model=UserResponse, summary="Update current user")
async def update_me(
    payload: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.name is not None:
        current_user.name = payload.name
    if payload.preferred_currency is not None:
        current_user.preferred_currency = payload.preferred_currency.upper()
    await db.flush()
    return current_user
