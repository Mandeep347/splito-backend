from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidCredentialsError,
    TokenExpiredError,
    UserAlreadyExistsError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.domain.user.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(self, payload: RegisterRequest) -> tuple[User, TokenResponse]:
        # Check uniqueness
        existing = await self.db.scalar(select(User).where(User.email == payload.email))
        if existing:
            raise UserAlreadyExistsError(f"Email {payload.email!r} is already registered.")

        user = User(
            name=payload.name,
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
        self.db.add(user)
        await self.db.flush()  # get the UUID without committing

        tokens = self._issue_tokens(str(user.id))
        return user, tokens

    async def login(self, payload: LoginRequest) -> TokenResponse:
        user = await self.db.scalar(select(User).where(User.email == payload.email))
        if not user or not verify_password(payload.password, user.password_hash):
            raise InvalidCredentialsError("Invalid email or password.")
        if not user.is_active:
            raise InvalidCredentialsError("Account is deactivated.")

        return self._issue_tokens(str(user.id))

    async def refresh(self, refresh_token: str) -> TokenResponse:
        from jose import JWTError

        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise TokenExpiredError("Refresh token is invalid or expired.")

        if payload.get("type") != "refresh":
            raise TokenExpiredError("Invalid token type.")

        return self._issue_tokens(payload["sub"])

    @staticmethod
    def _issue_tokens(user_id: str) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user_id),
            refresh_token=create_refresh_token(user_id),
        )
