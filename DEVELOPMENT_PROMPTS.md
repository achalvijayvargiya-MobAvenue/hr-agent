# HR Platform — Structured Development Prompts
#
# HOW TO USE THIS FILE
# ─────────────────────────────────────────────────────────────────────────────
# 1. Open a fresh Agent chat in Cursor.
# 2. Copy the prompt for the current step and paste it.
# 3. Verify the acceptance criteria before moving to the next step.
# 4. Steps must be done in order — each step assumes the previous is complete.
#
# PROJECT ROOT : c:\Code\Hr-agent
# STACK        : FastAPI + SQLAlchemy 2 + Pydantic v2 + Alembic (backend)
#                React + Vite + TypeScript + Tailwind CSS (frontend)
#                PostgreSQL (database)
# ─────────────────────────────────────────────────────────────────────────────

---

## PHASE 0 — Foundation & Infrastructure

---

### STEP 0.1 — Docker Compose + PostgreSQL

```
PROJECT: c:\Code\Hr-agent
TASK: Add Docker Compose with a PostgreSQL service so the app can run against
      Postgres instead of SQLite. Do NOT change any Python code yet.

DELIVERABLES:
1. Create `docker-compose.yml` at the project root with:
   - A `postgres` service using image `postgres:16-alpine`
   - Environment variables: POSTGRES_USER=hr_user, POSTGRES_PASSWORD=hr_pass,
     POSTGRES_DB=hr_platform
   - Port mapping: 5432:5432
   - A named volume `pgdata` for persistence
   - A `pgadmin` service using image `dpage/pgadmin4` on port 5050 (optional
     but helpful for dev), with email admin@hr.local and password admin
   - A `backend` service that builds from the project root using a
     `Dockerfile` (create a simple one), depends_on postgres, exposes port 8000,
     mounts the project directory as a volume, and runs
     `uvicorn hr_agent.main:app --host 0.0.0.0 --port 8000 --reload`

2. Create `Dockerfile` at the project root:
   - FROM python:3.12-slim
   - WORKDIR /app
   - Copy requirements.txt and run pip install
   - Copy the rest of the project
   - Default CMD: uvicorn hr_agent.main:app --host 0.0.0.0 --port 8000

3. Update `.env.example` (DO NOT touch the real `.env`):
   - Add: DATABASE_URL=postgresql://hr_user:hr_pass@localhost:5432/hr_platform
   - Add: SECRET_KEY=change-me-in-production
   - Add: ACCESS_TOKEN_EXPIRE_MINUTES=60
   - Keep all existing variables unchanged

4. Add to `requirements.txt`:
   - psycopg2-binary>=2.9.9
   - python-jose[cryptography]>=3.3.0
   - passlib[bcrypt]>=1.7.4
   - python-multipart>=0.0.9  (already present, keep it)

DO NOT CHANGE: Any file inside hr_agent/, any existing .env, migrations/.

VERIFY: `docker compose config` runs without errors.
```

---

### STEP 0.2 — Migrate database.py from SQLite to PostgreSQL

```
PROJECT: c:\Code\Hr-agent
TASK: Update the database layer so it works with PostgreSQL. The SQLite-specific
      WAL/foreign-key pragma block must be removed. Alembic must read DATABASE_URL
      from the environment.

CURRENT FILE TO EDIT: hr_agent/database.py
  - The `_build_engine()` function has an `if settings.database_url.startswith("sqlite"):` 
    block that sets WAL journal mode and foreign key pragmas. Remove the entire
    SQLite-specific block. Keep everything else identical.
  - The engine should just be: `create_engine(settings.database_url)`
  - Remove `connect_args` logic entirely (not needed for Postgres).

CURRENT FILE TO EDIT: alembic.ini
  - Find the line `sqlalchemy.url = ...` and replace it with:
    `sqlalchemy.url = %(DATABASE_URL)s`
  - This makes Alembic read from the environment variable.

CURRENT FILE TO EDIT: migrations/env.py
  - After the existing imports, add logic to override the Alembic sqlalchemy.url
    with the DATABASE_URL environment variable:
    ```python
    import os
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    ```
  - Place this before the `target_metadata = Base.metadata` line.

UPDATE `.env` file:
  - Change: DATABASE_URL=sqlite:///./hr_agent.db
  - To:     DATABASE_URL=postgresql://hr_user:hr_pass@localhost:5432/hr_platform

DO NOT CHANGE: Any model files, service files, API files, or schemas.

VERIFY:
  1. `docker compose up -d postgres` starts the Postgres container.
  2. `alembic upgrade head` runs all 3 existing migrations (001, 002, 003) 
     successfully against Postgres.
  3. `uvicorn hr_agent.main:app --reload --reload-dir hr_agent` starts without
     errors and GET /health returns {"status": "ok"}.
```

---

### STEP 0.3 — Smoke Test Existing Endpoints Against PostgreSQL

```
PROJECT: c:\Code\Hr-agent
TASK: Verify the existing API still works end-to-end with PostgreSQL by writing
      a quick smoke-test script. This is a verification step — create one new file.

DELIVERABLE:
Create `scripts/smoke_test.py` at the project root:
  - Use the `requests` library (already in requirements.txt).
  - Test sequence:
    1. GET http://localhost:8000/health → assert status 200, body {"status":"ok"}
    2. POST http://localhost:8000/jobs/upload with a small test PDF bytes payload
       OR just test that the endpoint returns 422 when no file is sent (to confirm
       the route is reachable).
    3. GET http://localhost:8000/matches/nonexistent-id → assert status 404 or 422.
  - Print PASS/FAIL for each check with a summary at the end.
  - Exit with code 1 if any check fails.

Also update `requirements.txt` to add:
  - httpx>=0.27.0  (already present — keep it)

DO NOT CHANGE: Any hr_agent/ files.

VERIFY: `python scripts/smoke_test.py` with the server running prints all PASS.
```

---

## PHASE 1 — User & Role Management

---

### STEP 1.1 — User and Role ORM Models + Migration

```
PROJECT: c:\Code\Hr-agent
TASK: Add User and Role database models and an Alembic migration for them.

EXISTING MODELS PATTERN (follow exactly):
  - All models live in hr_agent/models/
  - They inherit from `Base` imported from `hr_agent.database`
  - Primary keys are UUID strings generated with `default=lambda: str(uuid.uuid4())`
  - Timestamps use `mapped_column(DateTime, server_default=func.now(), nullable=False)`
  - hr_agent/models/__init__.py imports all models so Alembic sees them

DELIVERABLES:

1. Create `hr_agent/models/user.py`:
   - Class `User(Base)`, __tablename__ = "users"
   - Fields:
     id: str (UUID PK)
     email: str (String, unique=True, nullable=False, indexed)
     hashed_password: str (String, nullable=False)
     full_name: str | None (String, nullable=True)
     is_active: bool (Boolean, default=True, nullable=False)
     created_at: datetime
     updated_at: datetime (with onupdate=func.now())

2. Create `hr_agent/models/role.py`:
   - Class `Role(Base)`, __tablename__ = "roles"
   - Fields:
     id: str (UUID PK)
     name: str (String, unique=True, nullable=False) — e.g. "admin", "recruiter", "viewer"
     description: str | None (Text, nullable=True)
     created_at: datetime

3. Create `hr_agent/models/user_role.py`:
   - Class `UserRole(Base)`, __tablename__ = "user_roles"  (association table)
   - Fields:
     id: str (UUID PK)
     user_id: str (String, ForeignKey("users.id"), nullable=False)
     role_id: str (String, ForeignKey("roles.id"), nullable=False)
     assigned_at: datetime (server_default=func.now())
   - Add a UniqueConstraint on (user_id, role_id)

4. Update `hr_agent/models/__init__.py`:
   - Import User, Role, UserRole alongside the existing model imports so 
     Alembic's `Base.metadata` knows about them.

5. Create `migrations/versions/004_add_users_and_roles.py`:
   - Revision: "004", down_revision: "003"
   - upgrade(): create tables "users", "roles", "user_roles" with all columns
     and constraints matching the models above. Add indexes:
     ix_users_email on users(email)
     ix_user_roles_user on user_roles(user_id)
   - downgrade(): drop tables in reverse order (user_roles, roles, users)

DO NOT CHANGE: Any existing model files, any service files, any API files.

VERIFY:
  `alembic upgrade head` applies migration 004 without errors.
  `alembic downgrade -1` then `alembic upgrade head` works cleanly.
```

---

### STEP 1.2 — Security Utilities (Password Hashing + JWT)

```
PROJECT: c:\Code\Hr-agent
TASK: Create the security utility module that handles password hashing and
      JWT token creation/verification. This is pure utility code — no FastAPI
      routes yet.

EXISTING PATTERN:
  - hr_agent/config.py uses pydantic-settings with get_settings() cached by lru_cache
  - All configurable values are in Settings class

DELIVERABLES:

1. Update `hr_agent/config.py` — add these fields to the existing `Settings` class
   (do not remove any existing fields):
   - secret_key: str = "dev-secret-change-in-production"
   - algorithm: str = "HS256"
   - access_token_expire_minutes: int = 60

2. Create `hr_agent/core/__init__.py` (empty file to make it a package).

3. Create `hr_agent/core/security.py`:
   - Use `passlib.context.CryptContext` with schemes=["bcrypt"] for passwords.
   - Functions:
     a. `hash_password(plain: str) -> str`  — returns bcrypt hash
     b. `verify_password(plain: str, hashed: str) -> bool`  — verify
     c. `create_access_token(data: dict, expires_delta: timedelta | None = None) -> str`
        — creates a JWT using settings.secret_key and settings.algorithm.
          Default expiry = settings.access_token_expire_minutes minutes.
          Include "exp" claim.
     d. `decode_access_token(token: str) -> dict`
        — decodes and returns the payload. Raises `ValueError` with a clear
          message on expiry or invalid signature (catch jose.JWTError).
   - Import settings via `from hr_agent.config import get_settings`.
   - Add module-level logger: `logger = logging.getLogger(__name__)`

DO NOT CHANGE: Any model files, API files, database.py.

VERIFY:
  In a Python shell:
  ```python
  from hr_agent.core.security import hash_password, verify_password, create_access_token, decode_access_token
  h = hash_password("test123")
  assert verify_password("test123", h)
  token = create_access_token({"sub": "user@example.com"})
  payload = decode_access_token(token)
  assert payload["sub"] == "user@example.com"
  print("All security tests passed")
  ```
```

---

### STEP 1.3 — Auth API Endpoints (Register, Login, Me)

```
PROJECT: c:\Code\Hr-agent
TASK: Add authentication REST endpoints. Users can register, log in to get a
      JWT token, and fetch their own profile.

EXISTING PATTERNS TO FOLLOW:
  - Routes live in hr_agent/api/ as APIRouter instances
  - Routers are registered in hr_agent/main.py via app.include_router()
  - DB session is injected via `Depends(get_db)` imported from hr_agent.api.deps
  - Services are in hr_agent/services/ — keep business logic out of route handlers

DELIVERABLES:

1. Create `hr_agent/schemas/user.py` — Pydantic schemas:
   - `UserCreate(BaseModel)`: email: str, password: str, full_name: str | None = None
   - `UserResponse(BaseModel)`: id, email, full_name, is_active, roles: list[str], created_at
     — model_config = {"from_attributes": True}
   - `TokenResponse(BaseModel)`: access_token: str, token_type: str = "bearer"
   - `LoginRequest(BaseModel)`: email: str, password: str

2. Create `hr_agent/services/auth_service.py`:
   - Class `AuthService` with `__init__(self, db: Session)`
   - Methods:
     a. `register(data: UserCreate) -> User`
        — check email not already taken (raise ValueError if duplicate)
        — hash password, create User, commit, return User
     b. `login(email: str, password: str) -> str`
        — find user by email, verify password, raise ValueError on failure
        — call create_access_token({"sub": user.id, "email": user.email})
        — return the token string
     c. `get_user_by_id(user_id: str) -> User | None`
     d. `get_user_roles(user: User) -> list[str]`
        — query UserRole + Role for the user, return list of role name strings
   - Seed logic: create a default "admin" role on first use if it doesn't exist.

3. Create `hr_agent/api/auth.py`:
   - router = APIRouter(prefix="/auth", tags=["auth"])
   - POST /auth/register → body: UserCreate → response: UserResponse (201)
   - POST /auth/login → body: LoginRequest → response: TokenResponse (200)
   - GET /auth/me → requires bearer token → response: UserResponse (200)
     (For now, decode the token manually using decode_access_token from
      hr_agent.core.security; get_current_user dependency comes in step 1.4)

4. Update `hr_agent/main.py`:
   - Import and register the auth router:
     `from hr_agent.api import auth`
     `app.include_router(auth.router)`

DO NOT CHANGE: Any existing route files (jobs.py, candidates.py, matches.py, admin.py),
              any model files, database.py, config.py.

VERIFY:
  1. POST /auth/register with {"email":"admin@hr.local","password":"Admin1234!",
     "full_name":"Admin User"} returns 201 with a user object.
  2. POST /auth/login with same credentials returns {"access_token":"...","token_type":"bearer"}.
  3. GET /auth/me with Authorization: Bearer <token> returns the user profile.
  4. POST /auth/login with wrong password returns 401.
```

---

### STEP 1.4 — RBAC Dependencies (get_current_user + require_role)

```
PROJECT: c:\Code\Hr-agent
TASK: Create reusable FastAPI dependency functions for authentication and 
      role-based access control.

EXISTING PATTERNS:
  - Shared dependencies live in hr_agent/api/deps.py
  - FastAPI Depends() is used throughout existing routes
  - get_db() yields a Session

DELIVERABLES:

1. Create `hr_agent/core/permissions.py`:
   - `get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User`
     — Use `fastapi.security.OAuth2PasswordBearer(tokenUrl="/auth/login")` as oauth2_scheme
     — Decode the token using decode_access_token from hr_agent.core.security
     — Load the User from DB by ID (from token "sub" claim)
     — Raise HTTP 401 if token invalid or user not found
     — Raise HTTP 403 if user.is_active is False
   - `require_role(*role_names: str)` — returns a FastAPI dependency function:
     — The returned dependency takes `current_user: User = Depends(get_current_user)`
     — Queries UserRole + Role to check if user has any of the required roles
     — Raises HTTP 403 with message "Insufficient permissions" if not
     — Example usage: `Depends(require_role("admin"))` or `Depends(require_role("admin","recruiter"))`

2. Update `hr_agent/api/deps.py`:
   - Re-export `get_current_user` and `require_role` from hr_agent.core.permissions
     so all routers can import from the same place:
     ```python
     from hr_agent.core.permissions import get_current_user, require_role
     __all__ = [...existing..., "get_current_user", "require_role"]
     ```

3. Update `hr_agent/api/auth.py` — fix the GET /auth/me endpoint:
   - Replace the manual token decode with: `current_user: User = Depends(get_current_user)`

DO NOT CHANGE: Any model files, service files other than auth.py, database.py,
              existing route files (jobs, candidates, matches, admin).

VERIFY:
  1. GET /auth/me without a token returns 401.
  2. GET /auth/me with a valid token returns the user object.
  3. From Python: `from hr_agent.core.permissions import get_current_user, require_role`
     imports without error.
```

---

### STEP 1.5 — Lock Existing Routes Behind Authentication

```
PROJECT: c:\Code\Hr-agent
TASK: Protect all existing API routes so they require a valid JWT. The Streamlit
      UI (streamlit_app.py) may break — that is acceptable, it will be replaced
      by React.

ROUTES TO PROTECT (add `current_user: User = Depends(get_current_user)` to each):
  - hr_agent/api/jobs.py: upload_job, get_job, update_hard_checks
  - hr_agent/api/candidates.py: upload_candidate, get_candidate
  - hr_agent/api/matches.py: get_matches, recompute_match
  - hr_agent/api/admin.py: all existing admin endpoints

PATTERN FOR EACH ROUTE (example):
  ```python
  from hr_agent.api.deps import get_current_user
  from hr_agent.models.user import User

  @router.post("/upload", ...)
  async def upload_job(
      file: UploadFile,
      background_tasks: BackgroundTasks,
      db: Session = Depends(get_db),
      extraction_svc: ExtractionService = Depends(get_extraction_service),
      embedding_svc: EmbeddingService = Depends(get_embedding_service),
      current_user: User = Depends(get_current_user),   # ← ADD THIS
  ):
  ```
  The `current_user` parameter does not need to be used in the function body —
  its presence as a Depends() is enough to enforce authentication.

ADMIN-ONLY ROUTES — use require_role instead:
  - All routes in hr_agent/api/admin.py should use:
    `current_user: User = Depends(require_role("admin"))`

KEEP UNPROTECTED (these must remain public):
  - GET /health
  - POST /auth/register
  - POST /auth/login

DO NOT CHANGE: Any model files, service files, database.py, config.py, schemas.

VERIFY:
  1. GET /jobs/nonexistent-id without auth returns 401.
  2. GET /jobs/nonexistent-id with valid Bearer token returns 404 (not 401).
  3. POST /health returns 200 without any auth header.
```

---

### STEP 1.6 — User Management Admin Endpoints

```
PROJECT: c:\Code\Hr-agent
TASK: Add admin-only endpoints for managing users and assigning roles.

EXISTING PATTERNS:
  - Routers registered in hr_agent/main.py
  - Schemas in hr_agent/schemas/
  - Services in hr_agent/services/

DELIVERABLES:

1. Add to `hr_agent/schemas/user.py`:
   - `UserUpdate(BaseModel)`: full_name: str | None, is_active: bool | None
   - `RoleAssign(BaseModel)`: role_name: str

2. Update `hr_agent/services/auth_service.py` — add methods:
   - `list_users(skip: int = 0, limit: int = 50) -> list[User]`
   - `update_user(user_id: str, data: UserUpdate) -> User`
     — raise ValueError if user not found
   - `assign_role(user_id: str, role_name: str) -> UserRole`
     — create Role if it doesn't exist; create UserRole; skip if already assigned
   - `remove_role(user_id: str, role_name: str) -> None`
     — remove the UserRole row; raise ValueError if not found
   - `list_roles() -> list[Role]`

3. Create `hr_agent/api/users.py`:
   - router = APIRouter(prefix="/users", tags=["users"])
   - All routes require `Depends(require_role("admin"))`
   - GET  /users               → list_users, response: list[UserResponse]
   - GET  /users/{user_id}     → get single user, response: UserResponse
   - PUT  /users/{user_id}     → update user (full_name, is_active), response: UserResponse
   - POST /users/{user_id}/roles → body: RoleAssign → assign role, response: UserResponse
   - DELETE /users/{user_id}/roles/{role_name} → remove role, response: UserResponse
   - GET  /roles               → list all roles, response: list[dict]

4. Update `hr_agent/main.py`:
   - Import and register: `from hr_agent.api import users`
   - `app.include_router(users.router)`

DO NOT CHANGE: Existing model files, database.py, config.py, other API files.

VERIFY:
  1. As admin user: GET /users returns a list with at least the registered user.
  2. As admin: POST /users/{id}/roles with {"role_name":"recruiter"} assigns the role.
  3. GET /auth/me after role assignment returns roles: ["admin","recruiter"].
  4. As non-admin user: GET /users returns 403.
```

---

## PHASE 2 — Open Position / JD Module

---

### STEP 2.1 — Extend Job Model to Open Position

```
PROJECT: c:\Code\Hr-agent
TASK: Extend the existing `Job` model with open-position-specific fields and
      add a new Alembic migration. Do NOT rename the table or break existing code.

CURRENT FILE: hr_agent/models/job.py
  - Class Job, __tablename__ = "jobs"
  - Existing fields: id, title, normalized_role, experience_min/max, 
    must_have_skills, good_to_have_skills, department, industry, summary,
    employment_type, location, education_requirements, certifications,
    responsibilities, tools_and_technologies, seniority_level, hard_checks,
    raw_text, created_at

FIELDS TO ADD to hr_agent/models/job.py:
  - candidates_required: Mapped[int | None] = mapped_column(Integer, nullable=True)
    (how many people to hire for this position)
  - position_status: Mapped[str] = mapped_column(String, nullable=False, default="DRAFT")
    (values: DRAFT | OPEN | CLOSED)
  - created_by: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    (user who created the position — nullable so existing rows aren't broken)

UPDATE hr_agent/schemas/job.py:
  - Add `candidates_required: int | None = None` to `JobResponse`
  - Add `position_status: str = "DRAFT"` to `JobResponse`
  - Add `created_by: str | None = None` to `JobResponse`
  - Add a new schema `PositionStatusUpdate(BaseModel)` with field:
    `position_status: str` (must be one of DRAFT, OPEN, CLOSED — add a validator)

CREATE `migrations/versions/005_add_position_fields.py`:
  - Revision: "005", down_revision: "004"
  - upgrade():
    op.add_column("jobs", sa.Column("candidates_required", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("position_status", sa.String(), nullable=False,
                  server_default="DRAFT"))
    op.add_column("jobs", sa.Column("created_by", sa.String(), nullable=True))
    op.create_foreign_key("fk_jobs_created_by", "jobs", "users", ["created_by"], ["id"])
  - downgrade(): drop_constraint and drop_column in reverse order

DO NOT CHANGE: Any API files, service files, other model files, database.py.

VERIFY:
  `alembic upgrade head` applies migration 005 cleanly.
  `alembic downgrade -1` then `alembic upgrade head` round-trips without error.
```

---

### STEP 2.2 — Manual Position Entry Endpoint

```
PROJECT: c:\Code\Hr-agent
TASK: Add a new endpoint so recruiters can create an Open Position by filling
      in a form manually (no PDF needed). The position starts in DRAFT status
      and waits for approval before becoming OPEN.

EXISTING: hr_agent/api/jobs.py has POST /jobs/upload for PDF upload.
          Keep it working — add a new endpoint alongside it.

DELIVERABLES:

1. Add to `hr_agent/schemas/job.py`:
   - `PositionManualCreate(BaseModel)` — all fields optional except title:
     title: str
     normalized_role: str | None = None
     department: str | None = None
     industry: str | None = None
     location: str | None = None
     employment_type: str | None = None
     seniority_level: str | None = None
     experience_min: int | None = None
     experience_max: int | None = None
     candidates_required: int | None = None
     must_have_skills: list[str] = []
     good_to_have_skills: list[str] = []
     tools_and_technologies: list[str] = []
     education_requirements: list[str] = []
     certifications: list[str] = []
     responsibilities: list[str] = []
     summary: str | None = None

2. Update `hr_agent/api/jobs.py`:
   - Add new route: POST /jobs/manual → body: PositionManualCreate → response: JobResponse (201)
   - Route requires `current_user: User = Depends(get_current_user)`
   - Logic:
     a. Create a Job ORM object from the request body fields
     b. Set position_status = "DRAFT"
     c. Set created_by = current_user.id
     d. Add a ProcessingLog with entity_type="job", status=ProcessingStatus.STRUCTURED
        (manual entry is already structured — no extraction needed)
     e. Commit and return JobResponse
   - Import the new schema at the top of the file

DO NOT CHANGE: The existing /jobs/upload endpoint, any service files, any model files.

VERIFY:
  1. POST /jobs/manual (with auth token) with body:
     {"title": "Software Engineer", "normalized_role": "Software Engineer",
      "candidates_required": 3, "must_have_skills": ["Python","FastAPI"]}
     returns 201 with position_status = "DRAFT".
  2. GET /jobs/{id} returns the same position with all fields.
```

---

### STEP 2.3 — Position Approval Endpoint + Updated Upload Flow

```
PROJECT: c:\Code\Hr-agent
TASK: 
  (A) Add an approval endpoint so a recruiter can review extracted fields and
      approve them — moving status from DRAFT → OPEN.
  (B) Update the PDF upload flow so extracted jobs land in DRAFT (not EMBEDDED)
      until a user approves them.

DELIVERABLES:

1. Add to `hr_agent/schemas/job.py`:
   - `PositionApprove(BaseModel)` — same fields as PositionManualCreate plus:
     hard_checks: dict | None = None
     candidates_required: int | None = None
     (This lets the user edit extracted fields during the approval step)

2. Update `hr_agent/api/jobs.py`:

   (A) Add route: POST /jobs/{job_id}/approve
       - Requires: `current_user: User = Depends(get_current_user)`
       - Body: PositionApprove
       - Logic:
         1. Load the Job; return 404 if not found
         2. Update all provided non-None fields on the Job object
         3. Set job.position_status = "OPEN"
         4. Update the ProcessingLog to status STRUCTURED if it was DRAFT/EXTRACTED
         5. Commit and return JobResponse
       - Return 409 if position is already OPEN or CLOSED

   (B) Update the background task `_process_job()`:
       - After the LLM extraction succeeds and the job is committed as STRUCTURED,
         set job.position_status = "DRAFT" (not "OPEN")
       - Keep the embedding step unchanged
       - This means extracted positions sit in DRAFT until a human approves them

3. Add route: GET /jobs (list all positions)
   - Query params: status: str | None = None, created_by: str | None = None
   - Returns: list[JobResponse]
   - Requires authentication

DO NOT CHANGE: Existing upload route signature, any model files, service files.

VERIFY:
  1. Upload a JD PDF → status is DRAFT after processing completes.
  2. POST /jobs/{id}/approve with corrected fields → status changes to OPEN.
  3. GET /jobs?status=OPEN returns only open positions.
  4. POST /jobs/{id}/approve on an already-OPEN position returns 409.
```

---

## PHASE 3 — Candidate Source Module

---

### STEP 3.1 — Abstract CandidateSource Base Class + Registry

```
PROJECT: c:\Code\Hr-agent
TASK: Create the plugin architecture for candidate sources. This is pure Python
      OOP — no database or FastAPI changes yet. The goal is an ABC that all
      future sources implement, and a registry that discovers them.

DELIVERABLES:

1. Create `hr_agent/services/candidate_sources/__init__.py` (empty).

2. Create `hr_agent/services/candidate_sources/base.py`:
   ```python
   from abc import ABC, abstractmethod
   from dataclasses import dataclass, field

   @dataclass
   class CandidateRecord:
       """Normalised candidate data returned by any source."""
       source_name: str
       raw_text: str               # full text content of the CV/profile
       source_url: str | None = None
       metadata: dict = field(default_factory=dict)
       # Optional pre-filled fields (sources that return structured data can set these)
       name: str | None = None
       email: str | None = None
       location: str | None = None

   class CandidateSource(ABC):
       """
       Abstract base for all candidate sources.
       Each concrete source must implement fetch() and the name property.
       """

       @property
       @abstractmethod
       def name(self) -> str:
           """Unique machine-readable source identifier, e.g. 'local_kb'."""
           ...

       @property
       def display_name(self) -> str:
           """Human-readable label shown in the UI."""
           return self.name

       @abstractmethod
       def fetch(self, position_id: str, **kwargs) -> list[CandidateRecord]:
           """
           Fetch candidates relevant to the given position.
           Must return a list of CandidateRecord — empty list if none found.
           Should NOT raise exceptions; log and return [] on failure.
           """
           ...

       def is_available(self) -> bool:
           """Return False if the source is misconfigured or unavailable."""
           return True
   ```

3. Create `hr_agent/services/candidate_sources/registry.py`:
   ```python
   class SourceRegistry:
       """
       Holds all registered CandidateSource instances.
       Sources self-register by calling registry.register(source_instance).
       """
       _sources: dict[str, CandidateSource] = {}

       def register(self, source: CandidateSource) -> None: ...
       def get(self, name: str) -> CandidateSource | None: ...
       def list_available(self) -> list[CandidateSource]: ...
           # returns only sources where is_available() is True
       def fetch_all(self, position_id: str, source_names: list[str] | None = None) -> list[CandidateRecord]:
           # if source_names is None, fetch from all available sources
           # aggregate and return combined list
           ...

   # Module-level singleton
   source_registry = SourceRegistry()
   ```

DO NOT CHANGE: Any existing files.

VERIFY:
  ```python
  from hr_agent.services.candidate_sources.base import CandidateSource, CandidateRecord
  from hr_agent.services.candidate_sources.registry import source_registry
  print("Import successful")
  ```
```

---

### STEP 3.2 — LocalKBSource (Refactor Existing CV Upload into Plugin)

```
PROJECT: c:\Code\Hr-agent
TASK: Wrap the existing candidate-from-local-KB flow into a concrete
      CandidateSource implementation. The existing /candidates/upload endpoint
      must keep working unchanged.

DELIVERABLES:

1. Create `hr_agent/services/candidate_sources/local_kb.py`:
   - Class `LocalKBSource(CandidateSource)`
   - name = "local_kb"
   - display_name = "Local Knowledge Base"
   - __init__(self, db_session_factory): store the factory
   - fetch(self, position_id: str, **kwargs) -> list[CandidateRecord]:
     - Query ALL Candidate records from the database where normalized_role
       is not None (i.e., fully processed)
     - Convert each Candidate ORM object to a CandidateRecord:
       source_name = "local_kb"
       raw_text = candidate.raw_text or candidate.summary or ""
       name = candidate.name
       location = candidate.location
       metadata = {"candidate_id": candidate.id, "status": "existing"}
     - Return the list
   - is_available(self) -> bool: always True (local DB is always available)

2. Register LocalKBSource in `hr_agent/api/deps.py`:
   - Add a function `get_source_registry()` that:
     a. Creates a LocalKBSource with the SessionLocal factory
     b. Calls source_registry.register(local_kb_source)
     c. Returns source_registry
   - Use @lru_cache so registration only happens once

DO NOT CHANGE: hr_agent/api/candidates.py, hr_agent/models/candidate.py,
              hr_agent/services/extraction_service.py, hr_agent/services/embedding_service.py.

VERIFY:
  ```python
  from hr_agent.services.candidate_sources.local_kb import LocalKBSource
  from hr_agent.database import SessionLocal
  src = LocalKBSource(SessionLocal)
  print(src.name, src.is_available())  # local_kb True
  records = src.fetch("any-position-id")
  print(f"Found {len(records)} candidates")
  ```
```

---

### STEP 3.3 — LinkedInSource Stub + Plugin Pattern

```
PROJECT: c:\Code\Hr-agent
TASK: Add a LinkedIn source stub that demonstrates the plugin pattern. It reads
      from a local JSON file (no real LinkedIn API — that comes later). This
      proves new sources can be added without touching core code.

DELIVERABLES:

1. Create `hr_agent/services/candidate_sources/linkedin.py`:
   - Class `LinkedInSource(CandidateSource)`
   - name = "linkedin"
   - display_name = "LinkedIn"
   - __init__(self, data_file: str | None = None):
     - data_file defaults to "data/linkedin_candidates.json" relative to project root
     - Store the path
   - is_available(self) -> bool:
     - Return True only if the data file exists
   - fetch(self, position_id: str, **kwargs) -> list[CandidateRecord]:
     - If file doesn't exist, log a warning and return []
     - Load the JSON file — expected format: list of objects with keys:
       name, location, summary (raw_text), url (optional)
     - Convert each to CandidateRecord with source_name="linkedin"
     - Return the list

2. Create sample `data/linkedin_candidates.json` with 2-3 fake entries:
   ```json
   [
     {
       "name": "Jane Doe",
       "location": "Mumbai, India",
       "summary": "Senior software engineer with 8 years Python experience...",
       "url": "https://linkedin.com/in/janedoe"
     }
   ]
   ```

3. Update `hr_agent/api/deps.py` — extend `get_source_registry()`:
   - Also register LinkedInSource:
     ```python
     linkedin = LinkedInSource()
     source_registry.register(linkedin)
     ```
   - Since it's cached with @lru_cache this only runs once.

DO NOT CHANGE: base.py, registry.py, local_kb.py, any existing API files.

VERIFY:
  ```python
  from hr_agent.api.deps import get_source_registry
  reg = get_source_registry()
  print([s.name for s in reg.list_available()])  # ['local_kb', 'linkedin']
  ```
```

---

### STEP 3.4 — Add source_name to Candidate Model + Candidate Source API Endpoints

```
PROJECT: c:\Code\Hr-agent
TASK: 
  (A) Tag every Candidate with the source it came from.
  (B) Expose REST endpoints to list sources and trigger candidate fetching
      for a position.

DELIVERABLES — Part A:

1. Update `hr_agent/models/candidate.py`:
   - Add: `source_name: Mapped[str] = mapped_column(String, nullable=False, default="local_kb")`

2. Update `hr_agent/api/candidates.py` upload_candidate route:
   - When creating the Candidate ORM object, set source_name = "local_kb"
   - `candidate = Candidate(raw_text=raw_text, source_name="local_kb")`

3. Update `hr_agent/schemas/candidate.py` CandidateResponse:
   - Add: `source_name: str = "local_kb"`

4. Create `migrations/versions/006_add_candidate_source.py`:
   - Revision: "006", down_revision: "005"
   - upgrade(): op.add_column("candidates", sa.Column("source_name", sa.String(),
                nullable=False, server_default="local_kb"))
   - downgrade(): op.drop_column("candidates", "source_name")

DELIVERABLES — Part B:

5. Create `hr_agent/api/sources.py`:
   - router = APIRouter(prefix="/sources", tags=["sources"])
   - All routes require `Depends(get_current_user)`

   GET /sources
   → Returns list of all registered sources with: name, display_name, is_available
   → Use get_source_registry() from deps

   POST /sources/fetch/{position_id}
   → Query param: source_names: list[str] | None = None (if None, fetch from all)
   → Logic:
     a. Verify position exists (query Job table) — 404 if not
     b. Call source_registry.fetch_all(position_id, source_names)
     c. For each returned CandidateRecord where metadata.get("candidate_id") is None
        (i.e., it's a new candidate, not one already in local_kb):
        - Create a new Candidate ORM object with source_name=record.source_name,
          raw_text=record.raw_text, name=record.name, location=record.location
        - Add ProcessingLog with status EXTRACTED
        - Queue background extraction+embedding (same as /candidates/upload does)
     d. Return: {"position_id": ..., "sources_queried": [...], "new_candidates": N}

6. Update `hr_agent/main.py`:
   - Import and register sources router

DO NOT CHANGE: base.py, registry.py, local_kb.py, linkedin.py, matches.py.

VERIFY:
  1. `alembic upgrade head` applies migration 006.
  2. GET /sources (with auth) lists local_kb and linkedin.
  3. POST /sources/fetch/{valid_position_id} returns a JSON response with counts.
```

---

## PHASE 4 — Matching & Ranking Enhancements

---

### STEP 4.1 — Add top_k and source_filter to Matching Pipeline

```
PROJECT: c:\Code\Hr-agent
TASK: Extend the matching API to support (a) filtering candidates by source and
      (b) returning only the top K ranked results.

EXISTING: hr_agent/services/matching_service.py has MatchingService.run(db, job_id)
          hr_agent/api/matches.py has GET /matches/{job_id} and POST /recompute-match

DELIVERABLES:

1. Update `hr_agent/services/matching_service.py`:
   - Change signature of `run()` to:
     `def run(self, db: Session, job_id: str, source_filter: list[str] | None = None, top_k: int | None = None) -> list[MatchResult]:`
   - In Stage 1 (Hard Filters), when loading candidates:
     CURRENT: `db.query(Candidate).filter(Candidate.normalized_role.isnot(None)).all()`
     NEW:
     ```python
     query = db.query(Candidate).filter(Candidate.normalized_role.isnot(None))
     if source_filter:
         query = query.filter(Candidate.source_name.in_(source_filter))
     candidates = query.all()
     ```
   - After the final ranked list is built, if top_k is not None:
     `ranked = ranked[:top_k]`
   - All other logic stays identical.

2. Update `hr_agent/schemas/match.py`:
   - Update `MatchEntry` to add: `source_name: str | None = None`
   - Update `RecomputeRequest` to add:
     `source_filter: list[str] | None = None`
     `top_k: int | None = None`

3. Update `hr_agent/api/matches.py`:
   - GET /matches/{job_id}: add query params `top_k: int | None = None`,
     `source_filter: str | None = None` (comma-separated string, split to list)
   - When calling matching_svc.run(), pass these params.
   - In `_build_match_response()`, populate `source_name` on each MatchEntry:
     - After loading candidates, build a map: `source_map = {c.id: c.source_name for c in candidates}`
     - Set `source_name=source_map.get(result.candidate_id)` on each MatchEntry
   - POST /recompute-match: pass body.source_filter and body.top_k to matching_svc.run()

DO NOT CHANGE: Hard filter logic, scoring weights, LLM rerank logic, embedding logic.

VERIFY:
  1. GET /matches/{job_id}?top_k=5 returns at most 5 ranked candidates.
  2. GET /matches/{job_id}?source_filter=local_kb returns only local KB candidates.
  3. Existing GET /matches/{job_id} with no params still works as before.
```

---

### STEP 4.2 — Score Breakdown in Match Response

```
PROJECT: c:\Code\Hr-agent
TASK: Add a structured score_breakdown object to each MatchEntry so the frontend
      can display a visual breakdown of how the final score was computed.

EXISTING: hr_agent/schemas/match.py MatchEntry has individual score fields
          (rule_score, vector_score, llm_score, final_score) as flat floats.

DELIVERABLES:

1. Update `hr_agent/schemas/match.py`:
   - Add new model:
     ```python
     class ScoreBreakdown(BaseModel):
         rule_score: float | None
         vector_score: float | None
         llm_score: float | None
         final_score: float | None
         rule_weight: float
         vector_weight: float
         llm_weight: float
         # Human-readable: "40% rule + 20% vector + 40% LLM = 0.82"
         summary: str
     ```
   - Update `MatchEntry` to add: `score_breakdown: ScoreBreakdown | None = None`
   - Keep the existing flat score fields for backwards compatibility.

2. Update `hr_agent/api/matches.py` — `_build_match_response()`:
   - Import settings: `from hr_agent.config import get_settings`
   - For each ranked MatchEntry, compute and attach score_breakdown:
     ```python
     sw = get_settings().score_weights
     breakdown = ScoreBreakdown(
         rule_score=result.rule_score,
         vector_score=result.vector_score,
         llm_score=result.llm_score,
         final_score=result.final_score,
         rule_weight=sw.rule,
         vector_weight=sw.vector,
         llm_weight=sw.llm,
         summary=f"{int(sw.rule*100)}% rule + {int(sw.vector*100)}% vector + "
                 f"{int(sw.llm*100)}% LLM = {result.final_score:.2f}" if result.final_score else "N/A"
     )
     ```
   - Set entry.score_breakdown = breakdown for ranked entries only.

DO NOT CHANGE: MatchingService, any model files, database.py, config.py.

VERIFY:
  GET /matches/{job_id} for a position with ranked results returns entries where
  score_breakdown.summary looks like "40% rule + 20% vector + 40% LLM = 0.82".
```

---

## PHASE 5 — React Frontend

---

### STEP 5.1 — React App Scaffold (Vite + TypeScript + Tailwind)

```
PROJECT: c:\Code\Hr-agent
TASK: Create the React frontend application scaffold. The backend runs at
      http://localhost:8000. The frontend will run at http://localhost:5173 (Vite dev).

DELIVERABLES:

1. Create the frontend inside the project: `cd c:\Code\Hr-agent && npm create vite@latest frontend -- --template react-ts`

2. Inside `frontend/`, install dependencies:
   npm install
   npm install axios react-router-dom @tanstack/react-query
   npm install -D tailwindcss @tailwindcss/vite

3. Configure Tailwind in `frontend/vite.config.ts`:
   ```ts
   import { defineConfig } from 'vite'
   import react from '@vitejs/plugin-react'
   import tailwindcss from '@tailwindcss/vite'
   export default defineConfig({
     plugins: [react(), tailwindcss()],
     server: { proxy: { '/api': 'http://localhost:8000' } }
   })
   ```

4. Create `frontend/src/index.css` with just:
   `@import "tailwindcss";`

5. Create `frontend/src/lib/api.ts`:
   - Axios instance with baseURL = "/api/v1" (we will add the /api/v1 prefix in phase 6;
     for now use "" as baseURL and the full path in each call)
   - Actually: `baseURL: "http://localhost:8000"` for now
   - Request interceptor: reads token from localStorage key "hr_token",
     adds it as `Authorization: Bearer <token>` header if present

6. Create `frontend/src/lib/auth.ts`:
   - `setToken(token: string): void` — saves to localStorage
   - `getToken(): string | null`
   - `clearToken(): void`
   - `isLoggedIn(): boolean`

7. Create `frontend/src/App.tsx`:
   - Use React Router with these routes (just stubs for now):
     /login         → <LoginPage />
     /               → redirect to /positions if logged in, else /login
     /positions      → <PositionsPage />  (stub: "Positions coming soon")
     /candidates     → <CandidatesPage /> (stub: "Candidates coming soon")
     /matches        → <MatchesPage />    (stub: "Matches coming soon")
     /users          → <UsersPage />      (stub: "Users coming soon")
   - Wrap everything in a `<QueryClientProvider>` from @tanstack/react-query

8. Update `hr_agent/main.py` to add CORS middleware:
   ```python
   from fastapi.middleware.cors import CORSMiddleware
   app.add_middleware(CORSMiddleware,
       allow_origins=["http://localhost:5173"],
       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
   ```

VERIFY:
  1. `cd frontend && npm run dev` starts without errors at localhost:5173.
  2. Browser shows the React app.
  3. API calls from the browser to localhost:8000 are not blocked by CORS.
```

---

### STEP 5.2 — Auth Module (Login Page + Protected Routes)

```
PROJECT: c:\Code\Hr-agent
TASK: Build the authentication UI — login form, JWT storage, protected route
      wrapper, and a nav sidebar with user info.

DELIVERABLES (all files inside frontend/src/):

1. Create `modules/auth/LoginPage.tsx`:
   - Clean centered card with email + password fields and a "Sign In" button
   - On submit: POST /auth/login with {email, password}
   - On success: save token via setToken(), redirect to /positions
   - On failure: show error message under the form
   - Loading state on the button while the request is in flight
   - Style with Tailwind — use a brand color of indigo-600

2. Create `modules/auth/useAuth.ts` (React Query hook):
   - `useCurrentUser()` — GET /auth/me, returns user object
   - `useLogin()` — mutation for POST /auth/login
   - `useLogout()` — clears token, redirects to /login

3. Create `components/ProtectedRoute.tsx`:
   - Checks isLoggedIn(); if false, redirects to /login
   - Renders children if logged in

4. Create `components/Sidebar.tsx`:
   - Left sidebar with nav links: Positions, Candidates, Sources, Matches, Users (admin only)
   - Shows current user email + a Logout button at the bottom
   - Active link highlighted in indigo-600
   - Users link only shows when user has "admin" role

5. Create `components/Layout.tsx`:
   - Wraps Sidebar + main content area
   - Used by all protected pages

6. Update `App.tsx`:
   - Wrap all non-login routes with ProtectedRoute
   - Wrap protected routes with Layout

VERIFY:
  1. Navigate to / → redirected to /login.
  2. Login with valid credentials → redirected to /positions page.
  3. Refreshing the page on /positions stays on /positions (token persists in localStorage).
  4. Clicking Logout clears token and redirects to /login.
```

---

### STEP 5.3 — Open Positions Module UI

```
PROJECT: c:\Code\Hr-agent
TASK: Build the Positions module — list of open positions, PDF upload, manual
      entry form, and the review/approve page where users confirm extracted fields.

DELIVERABLES (all inside frontend/src/modules/positions/):

1. `hooks/usePositions.ts`:
   - `usePositions(status?: string)` — GET /jobs?status=... 
   - `usePosition(id: string)` — GET /jobs/{id}
   - `useUploadPosition()` — POST /jobs/upload (multipart)
   - `useCreateManualPosition()` — POST /jobs/manual
   - `useApprovePosition()` — POST /jobs/{id}/approve
   - All use React Query (useQuery / useMutation)

2. `PositionsPage.tsx` — list view:
   - Header with title "Open Positions" + two buttons: "Upload JD" and "Create Manual"
   - Table/card list showing: title, department, status badge (colour-coded:
     DRAFT=yellow, OPEN=green, CLOSED=gray), candidates_required, created_at
   - Clicking a row navigates to /positions/{id}
   - Upload JD button opens a modal with a file picker (PDF only) + Upload button
   - Create Manual button opens a slide-over panel with the manual entry form

3. `ManualPositionForm.tsx` — form component (used in the slide-over):
   - Fields: Title*, Normalized Role, Department, Industry, Location,
     Employment Type, Seniority Level, Experience Min/Max, Candidates Required,
     Must-Have Skills (tag input), Good-to-Have Skills (tag input),
     Tools & Technologies (tag input), Summary (textarea)
   - On submit: calls useCreateManualPosition(), closes panel, refreshes list
   - * = required

4. `PositionDetailPage.tsx` — detail/approve view at /positions/:id:
   - Shows all extracted fields in editable inputs (pre-filled from API)
   - At the top: status badge + "Approve & Open Position" button (only if DRAFT)
   - On approve: calls useApprovePosition() with the edited field values
   - After approval, status badge changes to OPEN and button disappears
   - Hard Checks section (existing functionality — keep it)

VERIFY:
  1. /positions lists all positions from the API.
  2. Uploading a PDF creates a position in DRAFT status.
  3. Clicking "Approve & Open Position" changes status to OPEN.
  4. Creating a manual position and approving it works end-to-end.
```

---

### STEP 5.4 — Candidate Sources Module UI

```
PROJECT: c:\Code\Hr-agent
TASK: Build the Candidate Sources UI — shows available sources, lets users
      trigger candidate fetching for a position, and lists all fetched candidates.

DELIVERABLES (all inside frontend/src/modules/candidates/):

1. `hooks/useSources.ts`:
   - `useSources()` — GET /sources
   - `useFetchCandidates(positionId: string)` — POST /sources/fetch/{positionId}
   - `useCandidates()` — GET /candidates (add this endpoint to the backend
     in hr_agent/api/candidates.py if it doesn't exist: GET /candidates returning
     list[CandidateResponse] with optional ?source_name= filter)
   - `useCandidate(id: string)` — GET /candidates/{id}

2. `SourcesPage.tsx`:
   - Title "Candidate Sources"
   - Source cards in a grid: each shows name, display_name, availability badge
     (green dot = available, gray = unavailable)
   - "Fetch for Position" button opens a dropdown/modal to select an OPEN position,
     then triggers POST /sources/fetch/{positionId}
   - Shows a success toast with the number of new candidates queued

3. `CandidatesPage.tsx`:
   - Title "Candidates"
   - Filter bar: source dropdown, search by name
   - Table showing: name, current_title, location, source badge
     (color-coded: local_kb=blue, linkedin=sky-blue), years_experience, status
   - Clicking a row navigates to /candidates/{id}

4. `CandidateDetailPage.tsx`:
   - Shows all extracted fields in read-only view
   - Skill tags, employment history timeline, education list
   - Source badge prominently displayed

VERIFY:
  1. /candidates shows all candidates with their source badges.
  2. Triggering "Fetch for Position" shows a success count.
  3. Candidate detail page shows all structured data.
```

---

### STEP 5.5 — Matching & Results Module UI

```
PROJECT: c:\Code\Hr-agent
TASK: Build the Matching module — select a position, run matching, display
      ranked top-K results with score breakdowns.

DELIVERABLES (all inside frontend/src/modules/matches/):

1. `hooks/useMatches.ts`:
   - `useMatches(positionId: string, topK?: number, sourceFilter?: string[])` 
     — GET /matches/{positionId}?top_k=...&source_filter=...
   - `useRecompute()` — POST /recompute-match mutation

2. `MatchesPage.tsx` — main matching UI:
   - Left panel: position selector (dropdown of OPEN positions) + filters:
     - Top K slider (5–50, default 10)
     - Source filter (multi-select checkboxes from GET /sources)
     - "Run Matching" button
   - Right panel: results area

3. `MatchResultsList.tsx` — results display:
   - Shows "Top {K} Candidates for {position title}"
   - Ranked cards in order, each showing:
     - Rank badge (#1, #2, ...)
     - Candidate name + current title + source badge
     - Final score as a large number (e.g. "0.84")
     - Score breakdown bar:  
       Three horizontal segments (rule/vector/LLM) color-coded
       (rule=indigo, vector=sky, LLM=violet) proportional to weighted contribution
     - Explanation text (collapsible)
   - Filtered-out candidates section at the bottom (collapsed by default):
     - Shows candidate name + filter reason

4. Add route `/matches` to App.tsx pointing to MatchesPage, wrapped in Layout.

VERIFY:
  1. Select a position with candidates → click Run Matching → results appear.
  2. Score breakdown bars are visible and proportional.
  3. Changing Top K to 3 limits results to 3 candidates.
  4. Filtered candidates are shown at the bottom with their reasons.
```

---

### STEP 5.6 — User Management Module UI (Admin Only)

```
PROJECT: c:\Code\Hr-agent
TASK: Build the admin-only user management UI.

DELIVERABLES (all inside frontend/src/modules/users/):

1. `hooks/useUsers.ts`:
   - `useUsers()` — GET /users
   - `useUpdateUser()` — PUT /users/{id}
   - `useAssignRole()` — POST /users/{id}/roles
   - `useRemoveRole()` — DELETE /users/{id}/roles/{role_name}

2. `UsersPage.tsx`:
   - Only accessible to admin (redirect non-admins to /positions)
   - Table: email, full_name, role badges, is_active toggle, Actions column
   - "Invite User" button (just shows a modal with email + role fields for now,
     calls POST /auth/register)
   - Role badges are clickable: clicking the × on a badge removes that role
   - "Add Role" button per row opens a small dropdown of available roles
   - is_active toggle calls PUT /users/{id} to activate/deactivate

VERIFY:
  1. /users is accessible to admin, shows 403 page for non-admin.
  2. Toggling is_active on a user updates it.
  3. Adding/removing roles updates the badge list.
```

---

## PHASE 6 — Production Hardening

---

### STEP 6.1 — Standardise API Error Responses

```
PROJECT: c:\Code\Hr-agent
TASK: All API errors should return a consistent JSON shape so the frontend can
      handle them uniformly.

TARGET ERROR SHAPE:
  {
    "error": "NOT_FOUND",
    "message": "Job 'abc' not found.",
    "status_code": 404,
    "path": "/jobs/abc"
  }

DELIVERABLES:

1. Create `hr_agent/core/errors.py`:
   - Custom exception class: `HRAgentError(Exception)` with fields:
     status_code: int, error_code: str, message: str
   - Subclasses: NotFoundError (404), ValidationError (422), 
     ConflictError (409), ForbiddenError (403), UnauthorizedError (401)

2. Update `hr_agent/main.py`:
   - Register an exception handler for HRAgentError that returns JSONResponse
     with the standard shape above, using request.url.path for the path field
   - Register a handler for RequestValidationError (from fastapi) that wraps
     it in the same shape with error_code="VALIDATION_ERROR"
   - Register a generic Exception handler returning 500 with
     error_code="INTERNAL_ERROR" (but don't expose stack traces)

3. Gradually update `hr_agent/api/jobs.py`, `hr_agent/api/candidates.py`,
   `hr_agent/api/matches.py`, `hr_agent/api/users.py`, `hr_agent/api/auth.py`:
   - Replace all `raise HTTPException(status_code=404, ...)` with
     `raise NotFoundError(message="...")`
   - Replace all `raise HTTPException(status_code=409, ...)` with
     `raise ConflictError(message="...")`

VERIFY:
  1. GET /jobs/nonexistent returns:
     {"error":"NOT_FOUND","message":"Job 'nonexistent' not found.","status_code":404,...}
  2. GET /jobs/nonexistent with no auth returns:
     {"error":"UNAUTHORIZED","message":"Not authenticated","status_code":401,...}
```

---

### STEP 6.2 — API Versioning (/api/v1/ prefix)

```
PROJECT: c:\Code\Hr-agent
TASK: Add /api/v1/ prefix to all routes so the API is versioned for future
      breaking-change safety.

DELIVERABLES:

1. Update `hr_agent/main.py` create_app():
   - Change each include_router call to add the prefix:
     app.include_router(auth.router, prefix="/api/v1")
     app.include_router(jobs.router, prefix="/api/v1")
     app.include_router(candidates.router, prefix="/api/v1")
     app.include_router(matches.router, prefix="/api/v1")
     app.include_router(admin.router, prefix="/api/v1")
     app.include_router(users.router, prefix="/api/v1")
     app.include_router(sources.router, prefix="/api/v1")
   - Keep GET /health unversioned (mount it directly on app)

2. Update `frontend/src/lib/api.ts`:
   - Change baseURL to "http://localhost:8000/api/v1"
   - Update all fetch paths in all hooks to remove the /api/v1 prefix
     (it's now the base, so /jobs/upload not /api/v1/jobs/upload)

3. Update `scripts/smoke_test.py`:
   - Update all URL paths to include /api/v1/

DO NOT CHANGE: Router prefix values inside the router files themselves —
               the versioning prefix is added only in main.py.

VERIFY:
  1. GET http://localhost:8000/health → 200 (unversioned)
  2. GET http://localhost:8000/api/v1/jobs → 401 (versioned, needs auth)
  3. Frontend login and positions list still works.
```

---

### STEP 6.3 — Full Production Docker Compose

```
PROJECT: c:\Code\Hr-agent
TASK: Finalise docker-compose.yml to run the complete stack (Postgres + backend
      + frontend with Nginx) with a single `docker compose up`.

DELIVERABLES:

1. Create `frontend/Dockerfile`:
   - Multi-stage:
     Stage 1 (builder): node:20-alpine, WORKDIR /app, copy package*.json,
     run npm ci, copy rest, run npm run build
     Stage 2 (serve): nginx:alpine, copy built dist/ from builder to
     /usr/share/nginx/html, copy nginx.conf

2. Create `frontend/nginx.conf`:
   - Serve static files from /usr/share/nginx/html
   - All routes fall back to index.html (for React Router)
   - Proxy /api/ to http://backend:8000/api/

3. Update `docker-compose.yml`:
   - `postgres` service (from step 0.1 — keep as is)
   - `backend` service: build from project root, depends_on postgres,
     env_file: .env, ports: 8000:8000
     command: uvicorn hr_agent.main:app --host 0.0.0.0 --port 8000
     healthcheck: GET /health
   - `frontend` service: build from ./frontend, ports: 80:80,
     depends_on: backend
   - `pgadmin` service (optional, keep from step 0.1)

4. Create `.dockerignore` at project root:
   __pycache__, *.pyc, .env, hr_agent.db, logs/, node_modules,
   frontend/node_modules, frontend/dist

VERIFY:
  1. `docker compose build` completes without errors.
  2. `docker compose up -d` starts all services.
  3. http://localhost → React app loads.
  4. http://localhost/api/v1/health → {"status":"ok"}
  5. Login and full happy-path test works through the containerised stack.
```

---

### STEP 6.4 — Integration Tests (Auth + Matching Pipeline)

```
PROJECT: c:\Code\Hr-agent
TASK: Add integration tests that run against a real Postgres database (via
      pytest fixtures) covering the two most critical flows: auth and matching.

EXISTING: tests/ folder has test_matching_service.py, test_pdf_service.py, conftest.py

DELIVERABLES:

1. Update `tests/conftest.py`:
   - Add a `test_db` fixture that creates a fresh Postgres database for tests
     (use a separate DATABASE_URL pointing to a test DB, e.g. hr_platform_test)
   - Add a `client` fixture: TestClient wrapping the FastAPI app with the test DB
   - Add a `auth_headers` fixture: registers a test user, logs in, returns
     {"Authorization": "Bearer <token>"} dict
   - Add an `admin_headers` fixture: same but assigns "admin" role first

2. Create `tests/test_auth.py`:
   - test_register_success: POST /auth/register → 201
   - test_register_duplicate_email: second register with same email → 409
   - test_login_success: POST /auth/login → 200 with access_token
   - test_login_wrong_password: → 401
   - test_me_authenticated: GET /auth/me with token → 200
   - test_me_unauthenticated: GET /auth/me without token → 401

3. Create `tests/test_positions.py`:
   - test_create_manual_position: POST /jobs/manual (authed) → 201, status=DRAFT
   - test_approve_position: POST /jobs/{id}/approve → 200, status=OPEN
   - test_list_positions_by_status: GET /jobs?status=OPEN returns only OPEN ones

4. Update `requirements.txt`:
   - pytest-asyncio already present; add: pytest-httpx if not present

VERIFY:
  `pytest tests/ -v` — all tests pass.
  `pytest tests/test_auth.py -v` passes in under 10 seconds.
```

---

## QUICK REFERENCE — File Map

```
hr_agent/
├── api/
│   ├── admin.py          (existing — admin utils)
│   ├── auth.py           (phase 1.3 — login/register/me)
│   ├── candidates.py     (existing — cv upload)
│   ├── deps.py           (existing — service factories; extended in 1.4, 3.2)
│   ├── jobs.py           (existing — jd upload; extended in 2.2, 2.3)
│   ├── matches.py        (existing — ranking; extended in 4.1, 4.2)
│   ├── sources.py        (phase 3.4 — source list + fetch trigger)
│   └── users.py          (phase 1.6 — user CRUD admin)
├── core/
│   ├── errors.py         (phase 6.1 — standard error classes)
│   ├── permissions.py    (phase 1.4 — RBAC dependencies)
│   └── security.py       (phase 1.2 — JWT + password hashing)
├── models/
│   ├── candidate.py      (existing; source_name added in 3.4)
│   ├── embedding.py      (existing)
│   ├── job.py            (existing; extended in 2.1)
│   ├── match_result.py   (existing)
│   ├── processing_log.py (existing)
│   ├── role.py           (phase 1.1)
│   ├── user.py           (phase 1.1)
│   └── user_role.py      (phase 1.1)
├── schemas/
│   ├── candidate.py      (existing; source_name added in 3.4)
│   ├── job.py            (existing; extended in 2.1, 2.2, 2.3)
│   ├── match.py          (existing; extended in 4.1, 4.2)
│   └── user.py           (phase 1.3)
├── services/
│   ├── auth_service.py           (phase 1.3)
│   ├── candidate_sources/
│   │   ├── __init__.py           (phase 3.1)
│   │   ├── base.py               (phase 3.1)
│   │   ├── linkedin.py           (phase 3.3)
│   │   ├── local_kb.py           (phase 3.2)
│   │   └── registry.py           (phase 3.1)
│   ├── embedding_service.py      (existing — do not modify)
│   ├── extraction_service.py     (existing — do not modify)
│   ├── matching_service.py       (existing; source_filter+top_k in 4.1)
│   └── pdf_service.py            (existing — do not modify)
├── config.py             (existing; secret_key added in 1.2)
├── database.py           (existing; SQLite pragmas removed in 0.2)
├── logging_config.py     (existing — do not modify)
└── main.py               (existing; routers added each phase)
migrations/
├── versions/
│   ├── 001_initial_schema.py
│   ├── 002_add_new_extraction_fields.py
│   ├── 003_add_hard_checks.py
│   ├── 004_add_users_and_roles.py     (phase 1.1)
│   ├── 005_add_position_fields.py     (phase 2.1)
│   └── 006_add_candidate_source.py    (phase 3.4)
frontend/
├── src/
│   ├── components/
│   │   ├── Layout.tsx              (phase 5.2)
│   │   ├── ProtectedRoute.tsx      (phase 5.2)
│   │   └── Sidebar.tsx             (phase 5.2)
│   ├── lib/
│   │   ├── api.ts                  (phase 5.1)
│   │   └── auth.ts                 (phase 5.1)
│   ├── modules/
│   │   ├── auth/                   (phase 5.2)
│   │   ├── candidates/             (phase 5.4)
│   │   ├── matches/                (phase 5.5)
│   │   ├── positions/              (phase 5.3)
│   │   └── users/                  (phase 5.6)
│   └── App.tsx                     (phase 5.1)
scripts/
└── smoke_test.py                   (phase 0.3)
docker-compose.yml                  (phase 0.1, completed in 6.3)
Dockerfile                          (phase 0.1)
```
