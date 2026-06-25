"""
FastAPI dependency functions for authentication and role-based access control.
"""
import logging

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from hr_agent.core.errors import ForbiddenError, UnauthorizedError
from hr_agent.core.security import decode_access_token
from hr_agent.database import get_db
from hr_agent.models.role import Role
from hr_agent.models.user import User
from hr_agent.models.user_role import UserRole

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency — decode the Bearer token and return the authenticated User.
    Raises 401 if the token is missing, expired, or the user is not found.
    Raises 403 if the user account is inactive.
    """
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise UnauthorizedError(message=str(exc))

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise UnauthorizedError(message="Token missing subject claim.")

    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        raise UnauthorizedError(message="User not found.")

    if not user.is_active:
        raise ForbiddenError(message="Inactive user account.")

    return user


def require_role(*role_names: str):
    """
    Return a FastAPI dependency that enforces at least one of the given roles.

    Usage:
        current_user: User = Depends(require_role("admin"))
        current_user: User = Depends(require_role("admin", "recruiter"))
    """
    def _dependency(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        has_role = (
            db.query(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(
                UserRole.user_id == current_user.id,
                Role.name.in_(role_names),
            )
            .first()
        )
        if not has_role:
            raise ForbiddenError(message="Insufficient permissions.")
        return current_user

    return _dependency
