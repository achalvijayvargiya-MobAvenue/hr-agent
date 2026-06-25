"""
Authentication service: user registration, login, and role management.
"""
import logging

from sqlalchemy.orm import Session

from hr_agent.core.security import create_access_token, hash_password, verify_password
from hr_agent.models.role import Role
from hr_agent.models.user import User
from hr_agent.models.user_role import UserRole
from hr_agent.schemas.user import UserCreate, UserUpdate

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._ensure_default_roles()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _ensure_default_roles(self) -> None:
        """Create the default 'admin' role if it doesn't exist yet."""
        if not self._db.query(Role).filter_by(name="admin").first():
            self._db.add(Role(name="admin", description="Full system access"))
            self._db.commit()
            logger.info("Seeded default 'admin' role.")

    # ── Public API ────────────────────────────────────────────────────────────

    def register(self, data: UserCreate) -> User:
        """Create a new user. Raises ValueError if the email is already taken."""
        if self._db.query(User).filter_by(email=data.email).first():
            raise ValueError(f"Email already registered: {data.email}")
        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        logger.info("Registered new user email=%s id=%s", user.email, user.id)
        return user

    def login(self, email: str, password: str) -> str:
        """
        Verify credentials and return a JWT access token.
        Raises ValueError on bad email or wrong password.
        """
        user = self._db.query(User).filter_by(email=email).first()
        if not user or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid email or password")
        token = create_access_token({"sub": user.id, "email": user.email})
        logger.info("User logged in email=%s id=%s", user.email, user.id)
        return token

    def get_user_by_id(self, user_id: str) -> User | None:
        """Return the User with the given ID, or None if not found."""
        return self._db.query(User).filter_by(id=user_id).first()

    def get_user_roles(self, user: User) -> list[str]:
        """Return the list of role name strings assigned to a user."""
        rows = (
            self._db.query(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user.id)
            .all()
        )
        return [row.name for row in rows]

    def list_users(self, skip: int = 0, limit: int = 50) -> list[User]:
        """Return a paginated list of all users."""
        return self._db.query(User).offset(skip).limit(limit).all()

    def update_user(self, user_id: str, data: UserUpdate) -> User:
        """Update full_name and/or is_active for a user. Raises ValueError if not found."""
        user = self._db.query(User).filter_by(id=user_id).first()
        if not user:
            raise ValueError(f"User not found: {user_id}")
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.is_active is not None:
            user.is_active = data.is_active
        self._db.commit()
        self._db.refresh(user)
        logger.info("Updated user id=%s", user_id)
        return user

    def assign_role(self, user_id: str, role_name: str) -> UserRole:
        """Assign a role to a user. Creates the role if it doesn't exist. Skips if already assigned."""
        user = self._db.query(User).filter_by(id=user_id).first()
        if not user:
            raise ValueError(f"User not found: {user_id}")
        role = self._db.query(Role).filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name)
            self._db.add(role)
            self._db.commit()
            self._db.refresh(role)
            logger.info("Created new role name=%s", role_name)
        existing = self._db.query(UserRole).filter_by(user_id=user_id, role_id=role.id).first()
        if existing:
            return existing
        user_role = UserRole(user_id=user_id, role_id=role.id)
        self._db.add(user_role)
        self._db.commit()
        self._db.refresh(user_role)
        logger.info("Assigned role=%s to user_id=%s", role_name, user_id)
        return user_role

    def remove_role(self, user_id: str, role_name: str) -> None:
        """Remove a role from a user. Raises ValueError if the assignment is not found."""
        role = self._db.query(Role).filter_by(name=role_name).first()
        if not role:
            raise ValueError(f"Role not found: {role_name}")
        user_role = self._db.query(UserRole).filter_by(user_id=user_id, role_id=role.id).first()
        if not user_role:
            raise ValueError(f"User {user_id!r} does not have role {role_name!r}")
        self._db.delete(user_role)
        self._db.commit()
        logger.info("Removed role=%s from user_id=%s", role_name, user_id)

    def list_roles(self) -> list[Role]:
        """Return all roles defined in the system."""
        return self._db.query(Role).all()
