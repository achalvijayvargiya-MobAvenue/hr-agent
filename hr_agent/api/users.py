"""
Admin-only user management endpoints.

GET    /users                          — list all users
GET    /users/{user_id}               — get a single user
PUT    /users/{user_id}               — update full_name / is_active
POST   /users/{user_id}/roles         — assign a role
DELETE /users/{user_id}/roles/{role}  — remove a role
GET    /roles                          — list all roles
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from hr_agent.api.deps import get_db, require_role
from hr_agent.core.errors import NotFoundError
from hr_agent.models.user import User
from hr_agent.schemas.user import RoleAssign, UserResponse, UserUpdate
from hr_agent.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])
roles_router = APIRouter(prefix="/roles", tags=["users"])


# ── Helper ────────────────────────────────────────────────────────────────────

def _build_user_response(user: User, svc: AuthService) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        roles=svc.get_user_roles(user),
        created_at=user.created_at,
    )


# ── /users routes ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 50,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> list[UserResponse]:
    svc = AuthService(db)
    users = svc.list_users(skip=skip, limit=limit)
    return [_build_user_response(u, svc) for u in users]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> UserResponse:
    svc = AuthService(db)
    user = svc.get_user_by_id(user_id)
    if not user:
        raise NotFoundError(message="User not found.")
    return _build_user_response(user, svc)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    body: UserUpdate,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> UserResponse:
    svc = AuthService(db)
    try:
        user = svc.update_user(user_id, body)
    except ValueError as exc:
        raise NotFoundError(message=str(exc))
    return _build_user_response(user, svc)


@router.post("/{user_id}/roles", response_model=UserResponse)
def assign_role(
    user_id: str,
    body: RoleAssign,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> UserResponse:
    svc = AuthService(db)
    try:
        svc.assign_role(user_id, body.role_name)
    except ValueError as exc:
        raise NotFoundError(message=str(exc))
    user = svc.get_user_by_id(user_id)
    return _build_user_response(user, svc)


@router.delete("/{user_id}/roles/{role_name}", response_model=UserResponse)
def remove_role(
    user_id: str,
    role_name: str,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> UserResponse:
    svc = AuthService(db)
    try:
        svc.remove_role(user_id, role_name)
    except ValueError as exc:
        raise NotFoundError(message=str(exc))
    user = svc.get_user_by_id(user_id)
    return _build_user_response(user, svc)


# ── /roles routes ─────────────────────────────────────────────────────────────

@roles_router.get("", response_model=list[dict])
def list_roles(
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> list[dict]:
    svc = AuthService(db)
    roles = svc.list_roles()
    return [{"id": r.id, "name": r.name, "description": getattr(r, "description", None)} for r in roles]
