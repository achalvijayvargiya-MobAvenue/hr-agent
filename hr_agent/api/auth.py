"""
Authentication routes.

POST /auth/register  — create a new user account
POST /auth/login     — exchange credentials for a JWT
GET  /auth/me        — return the current user's profile
"""
import logging

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from hr_agent.api.deps import get_current_user, get_db
from hr_agent.config import get_settings
from hr_agent.core.errors import ConflictError, UnauthorizedError
from hr_agent.models.user import User
from hr_agent.schemas.user import LoginRequest, TokenResponse, UserCreate, UserResponse, ForgotPasswordRequest, ResetPasswordRequest
from hr_agent.services.auth_service import AuthService
from hr_agent.services.email_service import EmailService

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


@router.post("/forgot-password")
def forgot_password(
    body: ForgotPasswordRequest, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    svc = AuthService(db)
    try:
        token = svc.generate_password_reset_token(body.email)
        frontend_url = get_settings().frontend_url.rstrip('/')
        reset_link = f"{frontend_url}/reset-password?token={token}"
        email_svc = EmailService()
        background_tasks.add_task(email_svc.send_reset_password_email, body.email, reset_link)
    except ValueError as exc:
        # Don't reveal if user exists or not for security, just log it.
        logger.debug(f"Forgot password requested for non-existent email: {body.email}")
    return {"message": "If that email is registered, we have sent a password reset link to it."}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    svc = AuthService(db)
    try:
        svc.reset_password(body.token, body.new_password)
    except ValueError as exc:
        raise UnauthorizedError(message=str(exc))
    return {"message": "Password has been successfully reset."}
