import uuid
from pydantic import BaseModel, EmailStr, Field


# ─── Auth ────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# ─── Email Verification ───────────────────────────────────────────────────────

class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=1)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


# ─── Password Reset ───────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


# ─── User ────────────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    preferred_currency: str
    is_active: bool
    is_email_verified: bool

    model_config = {"from_attributes": True}


class UpdateUserRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    preferred_currency: str | None = Field(None, min_length=3, max_length=3)


# ─── Generic message response ─────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
