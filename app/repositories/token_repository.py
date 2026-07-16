import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.token.models import TokenType, UserToken
from app.repositories.base import BaseRepository


class TokenRepository(BaseRepository[UserToken]):
    model = UserToken

    async def create_token(
        self,
        user_id: uuid.UUID,
        token_type: str,
        expires_delta: timedelta,
    ) -> UserToken:
        """
        Invalidates any existing unused tokens of same type for this user,
        then creates a fresh one.
        """
        # Invalidate previous tokens of same type
        await self.db.execute(
            update(UserToken)
            .where(
                UserToken.user_id == user_id,
                UserToken.token_type == token_type,
                UserToken.is_used == False,  # noqa: E712
            )
            .values(is_used=True)
        )

        token_value = secrets.token_urlsafe(48)  # 64-char URL-safe string
        expires_at = datetime.now(timezone.utc) + expires_delta

        token = UserToken(
            user_id=user_id,
            token=token_value,
            token_type=token_type,
            expires_at=expires_at,
            is_used=False,
        )
        self.db.add(token)
        await self.db.flush()
        return token

    async def get_valid_token(
        self, token_value: str, token_type: str
    ) -> UserToken | None:
        """
        Returns token only if:
          - token value matches
          - correct type
          - not used
          - not expired
        """
        now = datetime.now(timezone.utc)
        return await self.db.scalar(
            select(UserToken).where(
                UserToken.token == token_value,
                UserToken.token_type == token_type,
                UserToken.is_used == False,  # noqa: E712
                UserToken.expires_at > now,
            )
        )

    async def consume_token(self, token: UserToken) -> None:
        """Mark a token as used — single-use enforcement."""
        token.is_used = True
        await self.db.flush()
