"""
Authentication routes.

POST /auth/register  — create a new user account
POST /auth/login     — exchange credentials for a JWT
GET  /auth/me        — return the current user's profile
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from hr_agent.api.deps import get_current_user, get_db
from hr_agent.core.errors import ConflictError, UnauthorizedError
from hr_agent.models.user import User
from hr_agent.schemas.user import LoginRequest, TokenResponse, UserCreate, UserResponse
from hr_agent.services.auth_service import AuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# ── Helper ────────────────────────────────────────────────────────────────────

def _build_user_response(user, svc: AuthService) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        roles=svc.get_user_roles(user),
        created_at=user.created_at,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=201)
def register(body: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    svc = AuthService(db)
    try:
        user = svc.register(body)
    except ValueError as exc:
        raise ConflictError(message=str(exc))
    return _build_user_response(user, svc)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    svc = AuthService(db)
    try:
        token = svc.login(body.email, body.password)
    except ValueError as exc:
        raise UnauthorizedError(message=str(exc))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    svc = AuthService(db)
    return _build_user_response(current_user, svc)
