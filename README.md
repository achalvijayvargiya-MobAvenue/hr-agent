# HR Agent

Match candidate CVs to job descriptions using **LLM extraction**, **vector embeddings**, and **rule-based scoring** — all in a single SQLite file, no server required.

---

## Project structure

```
hr_agent/
├── config.py               # All tuneable settings (env-driven)
├── database.py             # SQLAlchemy engine + session factory
├── main.py                 # FastAPI app factory
├── models/                 # SQLAlchemy ORM models
│   ├── job.py
│   ├── candidate.py
│   ├── embedding.py
│   ├── match_result.py
│   └── processing_log.py
├── schemas/                # Pydantic schemas (API + LLM)
│   ├── job.py
│   ├── candidate.py
│   └── match.py
├── services/               # Business logic (no FastAPI coupling)
│   ├── pdf_service.py      # PDF → plain text
│   ├── extraction_service.py   # LLM field extraction with retry
│   ├── embedding_service.py    # numpy BLOB embeddings + cosine sim
│   └── matching_service.py     # 4-stage matching pipeline
├── api/                    # FastAPI routers
│   ├── deps.py             # Shared dependencies
│   ├── jobs.py
│   ├── candidates.py
│   └── matches.py
└── prompts/                # Prompt templates (edit without touching code)
    ├── jd_extraction.txt
    ├── cv_extraction.txt
    └── reranking.txt
migrations/                 # Alembic migrations
tests/                      # pytest test suite
frontend/                   # React + TypeScript + Vite UI
├── src/                    # Pages, components, API client
├── package.json
└── vite.config.ts          # Dev server + API proxy to :8000
```

---

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...
```

### 3. Create the database

```bash
# Option A — Alembic (recommended, supports future migrations)
alembic upgrade head

# Option B — auto-create on startup (handled automatically)
# Tables are created at first startup via Base.metadata.create_all
```

### 4. Run the server

```bash
uvicorn hr_agent.main:app --reload
```

API docs available at: http://localhost:8000/docs

---

## Frontend setup

The web UI lives in `frontend/`. It is a React + TypeScript app built with Vite and Tailwind CSS.

### Prerequisites

- **Node.js 20+** (LTS recommended — matches the frontend Docker image)
- **npm** (included with Node.js)
- **Backend running** on `http://localhost:8000` (see [Quick start](#quick-start) above)

### 1. Install dependencies

```bash
cd frontend
npm install
```

### 2. Start the development server

```bash
npm run dev
```

Open **http://localhost:5173** in your browser.

The Vite dev server proxies `/api` to the backend at `http://localhost:8000`, so make sure the API is up before using the UI:

```bash
# from the project root (in a separate terminal)
uvicorn hr_agent.main:app --reload
```

Sign in at `/login` with your backend credentials.

### Other frontend commands

| Command | Description |
|---------|-------------|
| `npm run build` | Type-check and build a production bundle to `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | Run ESLint |

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/jobs/upload` | Upload a JD PDF — returns `job_id` immediately, processes in background |
| `GET` | `/jobs/{job_id}` | Get structured job with processing status |
| `POST` | `/candidates/upload` | Upload a CV PDF — same async pattern |
| `GET` | `/candidates/{id}` | Get structured candidate with processing status |
| `GET` | `/matches/{job_id}` | Ranked candidate list for a job (runs pipeline on first call) |
| `POST` | `/recompute-match` | Force a fresh pipeline run (`{"job_id": "..."}`) |
| `GET` | `/health` | Liveness check |

### Processing status flow

```
PENDING → EXTRACTED → STRUCTURED → EMBEDDED
                                  ↓
                               FAILED (on any error)
```

Poll `GET /jobs/{id}` or `GET /candidates/{id}` until status is `EMBEDDED` before running matching.

---

## Configuration reference

All values have sensible defaults — only `OPENAI_API_KEY` is required.

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | **Required** |
| `DATABASE_URL` | `sqlite:///./hr_agent.db` | SQLite file path |
| `EXTRACTION_MODEL` | `gpt-4o` | Model for JD/CV field extraction |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `RERANK_MODEL` | `gpt-4o` | Model for LLM re-ranking |
| `MAX_EXTRACTION_RETRIES` | `2` | Pydantic validation retries |
| `TOP_N_FOR_RERANK` | `20` | How many candidates reach the LLM stage |
| `RULE_WEIGHT` | `0.4` | Final score weight for rule stage |
| `VECTOR_WEIGHT` | `0.2` | Final score weight for vector stage |
| `LLM_WEIGHT` | `0.4` | Final score weight for LLM stage |
| `SKILL_WEIGHT` | `0.4` | Rule sub-weight: skill match |
| `EXPERIENCE_WEIGHT` | `0.2` | Rule sub-weight: experience |
| `ROLE_WEIGHT` | `0.2` | Rule sub-weight: role match |
| `INDUSTRY_WEIGHT` | `0.2` | Rule sub-weight: industry match |

> Weights must sum to 1.0 within each group — the app validates this at startup.

---

## Matching pipeline

```
1. Hard filters    eliminate candidates outside experience band or missing must-have skills
2. Rule score      Skill 40% + Experience 20% + Role 20% + Industry 20%
3. Vector score    cosine_similarity(jd_embedding, cv_embedding) via numpy
4. LLM rerank      GPT-4o rates top-N candidates 0–100 with a brief explanation

Final score = 0.4 × rule + 0.2 × vector + 0.4 × (llm / 100)
```

---

## Running tests

```bash
pytest tests/ -v
```

Tests use an in-memory SQLite database. No OpenAI key is required for the unit test suite.

---

## Adding a future migration

```bash
alembic revision --autogenerate -m "add new column"
alembic upgrade head
```
