from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domain.user.models import User
from app.middleware.auth import get_current_user
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UpdateUserRequest,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.auth_service import AuthService

router = APIRouter()


def _svc(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


# ─── Auth ─────────────────────────────────────────────────────────────────────

@router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Creates a new account and sends a verification email. "
        "User must verify email before logging in."
    ),
)
async def register(
    payload: RegisterRequest,
    svc: AuthService = Depends(_svc),
):
    user, _ = await svc.register(payload)
    return user


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Login and get tokens",
    description="Returns JWT access + refresh tokens. Requires verified email.",
)
async def login(
    payload: LoginRequest,
    svc: AuthService = Depends(_svc),
):
    return await svc.login(payload)


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh_token(
    payload: RefreshRequest,
    svc: AuthService = Depends(_svc),
):
    return await svc.refresh(payload.refresh_token)


# ─── Email Verification ───────────────────────────────────────────────────────

@router.post(
    "/auth/verify-email",
    response_model=MessageResponse,
    summary="Verify email address",
    description="Submit the token received in the verification email.",
)
async def verify_email(
    payload: VerifyEmailRequest,
    svc: AuthService = Depends(_svc),
):
    return await svc.verify_email(payload.token)


@router.post(
    "/auth/resend-verification",
    response_model=MessageResponse,
    summary="Resend verification email",
    description=(
        "Sends a new verification email. "
        "Always returns success to prevent email enumeration."
    ),
)
async def resend_verification(
    payload: ResendVerificationRequest,
    svc: AuthService = Depends(_svc),
):
    return await svc.resend_verification(payload.email)


# ─── Password Reset ───────────────────────────────────────────────────────────

@router.post(
    "/auth/forgot-password",
    response_model=MessageResponse,
    summary="Request password reset email",
    description=(
        "Sends a reset link to the email if it exists. "
        "Always returns success to prevent email enumeration."
    ),
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    svc: AuthService = Depends(_svc),
):
    return await svc.forgot_password(payload.email)


@router.post(
    "/auth/reset-password",
    response_model=MessageResponse,
    summary="Reset password with token",
    description="Submit the token from the reset email and a new password.",
)
async def reset_password(
    payload: ResetPasswordRequest,
    svc: AuthService = Depends(_svc),
):
    return await svc.reset_password(payload.token, payload.new_password)


# ─── User ─────────────────────────────────────────────────────────────────────

@router.get(
    "/users/me",
    response_model=UserResponse,
    summary="Get current user",
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.patch(
    "/users/me",
    response_model=UserResponse,
    summary="Update current user",
)
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
