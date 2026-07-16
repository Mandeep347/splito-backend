from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.domain.token.models import TokenType
from app.domain.user.models import User
from app.repositories.token_repository import TokenRepository
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
)
from app.services.email_service import (
    send_password_reset_email,
    send_verification_email,
)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.token_repo = TokenRepository(db)

    # ── Register ──────────────────────────────────────────────────────────────

    async def register(
        self, payload: RegisterRequest
    ) -> tuple[User, TokenResponse]:
        existing = await self.db.scalar(
            select(User).where(User.email == payload.email)
        )
        if existing:
            raise UserAlreadyExistsError(
                f"Email {payload.email!r} is already registered."
            )

        user = User(
            name=payload.name,
            email=payload.email,
            password_hash=hash_password(payload.password),
            is_email_verified=False,   # must verify before login
        )
        self.db.add(user)
        await self.db.flush()

        # Create and send verification token (fire-and-forget)
        token_obj = await self.token_repo.create_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
            expires_delta=timedelta(
                hours=settings.email_verification_expire_hours
            ),
        )
        await send_verification_email(
            to_email=user.email,
            name=user.name,
            token=token_obj.token,
        )

        tokens = self._issue_tokens(str(user.id))
        return user, tokens

    # ── Login ─────────────────────────────────────────────────────────────────

    async def login(self, payload: LoginRequest) -> TokenResponse:
        user = await self.db.scalar(
            select(User).where(User.email == payload.email)
        )
        if not user or not verify_password(payload.password, user.password_hash):
            raise InvalidCredentialsError("Invalid email or password.")

        if not user.is_active:
            raise InvalidCredentialsError("Account is deactivated.")

        # Block unverified users
        if not user.is_email_verified:
            raise EmailNotVerifiedError(
                "Please verify your email address before logging in. "
                "Check your inbox for the verification link."
            )

        return self._issue_tokens(str(user.id))

    # ── Refresh ───────────────────────────────────────────────────────────────

    async def refresh(self, refresh_token: str) -> TokenResponse:
        from jose import JWTError

        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise TokenExpiredError("Refresh token is invalid or expired.")

        if payload.get("type") != "refresh":
            raise TokenExpiredError("Invalid token type.")

        return self._issue_tokens(payload["sub"])

    # ── Email Verification ────────────────────────────────────────────────────

    async def verify_email(self, token_value: str) -> MessageResponse:
        token_obj = await self.token_repo.get_valid_token(
            token_value, TokenType.EMAIL_VERIFICATION
        )
        if not token_obj:
            raise InvalidTokenError(
                "Verification link is invalid or has expired. "
                "Please request a new one."
            )

        # Mark email as verified
        user = await self.db.scalar(
            select(User).where(User.id == token_obj.user_id)
        )
        if not user:
            raise UserNotFoundError("User not found.")

        user.is_email_verified = True
        await self.token_repo.consume_token(token_obj)
        await self.db.flush()

        return MessageResponse(
            message="Email verified successfully. You can now log in."
        )

    async def resend_verification(self, email: str) -> MessageResponse:
        user = await self.db.scalar(
            select(User).where(User.email == email)
        )
        # Always return success — never leak whether email exists
        if not user:
            return MessageResponse(
                message="If that email is registered, a verification link has been sent."
            )
        if user.is_email_verified:
            return MessageResponse(message="Email is already verified.")

        token_obj = await self.token_repo.create_token(
            user_id=user.id,
            token_type=TokenType.EMAIL_VERIFICATION,
            expires_delta=timedelta(
                hours=settings.email_verification_expire_hours
            ),
        )
        await send_verification_email(
            to_email=user.email,
            name=user.name,
            token=token_obj.token,
        )
        return MessageResponse(
            message="If that email is registered, a verification link has been sent."
        )

    # ── Forgot Password ───────────────────────────────────────────────────────

    async def forgot_password(self, email: str) -> MessageResponse:
        user = await self.db.scalar(
            select(User).where(User.email == email)
        )
        # Always return success — never leak whether email exists
        if user and user.is_active:
            token_obj = await self.token_repo.create_token(
                user_id=user.id,
                token_type=TokenType.PASSWORD_RESET,
                expires_delta=timedelta(
                    minutes=settings.password_reset_expire_minutes
                ),
            )
            await send_password_reset_email(
                to_email=user.email,
                name=user.name,
                token=token_obj.token,
            )

        return MessageResponse(
            message=(
                "If that email is registered, a password reset link "
                "has been sent. Check your inbox."
            )
        )

    # ── Reset Password ────────────────────────────────────────────────────────

    async def reset_password(
        self, token_value: str, new_password: str
    ) -> MessageResponse:
        token_obj = await self.token_repo.get_valid_token(
            token_value, TokenType.PASSWORD_RESET
        )
        if not token_obj:
            raise InvalidTokenError(
                "Password reset link is invalid or has expired. "
                "Please request a new one."
            )

        user = await self.db.scalar(
            select(User).where(User.id == token_obj.user_id)
        )
        if not user:
            raise UserNotFoundError("User not found.")

        user.password_hash = hash_password(new_password)
        await self.token_repo.consume_token(token_obj)
        await self.db.flush()

        return MessageResponse(
            message="Password reset successfully. You can now log in."
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _issue_tokens(user_id: str) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user_id),
            refresh_token=create_refresh_token(user_id),
        )
