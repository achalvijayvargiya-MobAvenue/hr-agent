from datetime import datetime

from pydantic import BaseModel, field_validator


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email_domain(cls, v: str) -> str:
        if not v.endswith("@mobavenue.com"):
            raise ValueError("Only @mobavenue.com email addresses are allowed.")
        return v
class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    is_active: bool
    roles: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None


class RoleAssign(BaseModel):
    role_name: str
