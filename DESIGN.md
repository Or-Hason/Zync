# ZYNC - SYSTEM DESIGN DOCUMENT

## 1. SYSTEM OVERVIEW
Zync is an automated, AI-driven job hunting and application management system. It scrapes job listings, parses user CVs, evaluates match scores using LLMs (local and cloud), filters noise via a keyword blacklist, and manages the application lifecycle through a React + Tauri desktop application.

## 2. ARCHITECTURE

The system follows a modern desktop-web architecture:

- **Presentation Layer (Tauri + React):** A lightweight desktop application. React (TypeScript, Vite) handles the UI/UX; Tauri (Rust) provides the native OS shell and inter-process bridge.
- **Server Layer (FastAPI):** A Python 3.12+ async server handling scraping logic, business rules, and REST API endpoints. All I/O-bound operations are fully async (`asyncpg`, `httpx`, `aiofiles`).
- **AI Processing Layer:**
  - `Ollama (llama3:8b)`: Local inference for lightweight tasks — job content extraction, content classification, resume parsing. Zero API cost; data stays local.
  - `Gemini Flash (API)`: Cloud inference for complex reasoning — match scoring (0–100), rationale generation, skill gap analysis, _(Planned)_ CV tailoring, _(Planned)_ Cover Letter generation.
- **Data Layer (PostgreSQL 18):** Stores jobs, resumes, and user settings. Uses `asyncpg` driven by SQLAlchemy 2.0 (async ORM) with Alembic for schema migrations. Heavily utilizes `JSONB` for dynamic metadata (requirements, score details, settings).

## 3. AI RESPONSIBILITY ARCHITECTURE

A strict boundary separates the two AI layers to keep prompts simple, costs predictable, and behaviour deterministic:

| Concern | Ollama (local) | Gemini (cloud) |
| :--- | :--- | :--- |
| **Role** | Dumb extraction — pull structured fields from raw text | Smart reasoning — evaluate, compare, score |
| **Tasks** | Job field extraction (title, company, dates, requirements), resume parsing, content classification | Match scoring (0–100), rationale generation, skill gap analysis |
| **Prompt style** | Short, strict, schema-bound. Outputs are sanitized and length-capped before use. | Rich context (requirements JSONB + resume structured data). Output is validated against a Pydantic schema. |
| **Data sent** | Raw job posting or resume text (local inference — never leaves the machine) | Only `{ job_title, job_description, requirements, structured_resume_data }` — no raw text, no PII |
| **Failure mode** | Graceful fallback (missing fields default to `null`; unclassified input is treated as `VALID_JOB`) | Scoring returns `null` on failure; the job is still persisted without a score |

**Rule:** Ollama prompts must never perform reasoning or ranking. Gemini prompts must never perform raw text extraction. Mixing these responsibilities is a regression.

## 4. CORE WORKFLOWS

### 4.1 Job Discovery

1. **Manual Entry:** User pastes a URL or raw job text. The server fetches the HTML (URL path), extracts readable content with BeautifulSoup4, and enforces a content size cap.
2. **Auto-Scraping:** _(Planned)_ Scheduled scraping of predefined job boards (LinkedIn, Glassdoor, etc.).
3. **Parsing:** Extracted text is passed to Ollama to produce structured fields (company, title, description, requirements, classification, published date).

### 4.2 Evaluation Pipeline

The scoring pipeline runs in a strict order to minimize LLM calls and DB writes on bad input:

1. **Content Classification Gate** — Ollama classifies the raw content as one of: `VALID_JOB`, `LOGIN_WALL`, `IRRELEVANT`, `INSUFFICIENT_DATA`. Non-valid classifications return HTTP 422 immediately — no DB write occurs.
2. **Duplicate Detection** — TF-IDF cosine similarity on `raw_content` against the 500 most recent jobs in the DB. The duplicate chance (0–100) and matched job status are recorded on the new row.
3. **Score Cache Check** — TF-IDF cosine similarity (threshold > 0.90) on `job_title + job_description` against all jobs previously scored with the active resume. A cache hit copies the prior score, inserts a new row marked `is_duplicate=True`, and returns immediately — skipping blacklist check and Gemini.
4. **Blacklist Filter** — Case-insensitive keyword match on title and description. A hit auto-rejects the job (persisted with `status=auto_rejected`) and returns HTTP 422. The user may bypass this gate with `force_score=true` (controlled by their stored bypass preference).
5. **Active Resume Guard** — If no resume is currently active, the job is persisted without a score and HTTP 400 is returned. The client uses the returned `job_id` to re-trigger scoring once a resume is selected.
6. **Gemini Scoring** — The job title, description, and requirements JSONB are sent alongside the resume's `structured_data` to Gemini Flash, which returns a `match_score` (0–100), `rationale`, `matched_skills`, and `missing_skills`.
7. **Persist & Auto-Reject** — A new job row is always inserted (never updated). Jobs with `match_score < 40` receive `status=auto_rejected` automatically.
8. **System Advice** — A user-facing advice string is generated from the score, duplicate status, and matched job status; returned in the API response for immediate display.

### 4.3 Action & Management

1. Users view and manage scored jobs in the Dashboard.
2. The active resume can be switched at any time; the frontend performs a read-only cache check to show the cached score for the selected resume without re-scoring.
3. _(Planned)_ High-match jobs trigger local push notifications via Tauri.
4. _(Planned)_ One-click tailored CV generation and semi-auto application submission.

## 5. DATABASE SCHEMA (PostgreSQL 18)

### Table: `jobs`

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Primary key. |
| `company_name` | VARCHAR(255) | Nullable. Extracted company name. |
| `job_title` | VARCHAR(255) | Nullable. Extracted job title. |
| `company_description` | TEXT | Nullable. |
| `job_description` | TEXT | Nullable. Summarized job description. |
| `raw_content` | TEXT | Nullable. Normalized Ollama-extracted core posting text; used for TF-IDF duplicate detection. |
| `requirements` | JSONB | Nullable. Structured requirements (skills, years, education, etc.). |
| `source_type` | VARCHAR(50) | `'manual'` or `'auto'`. |
| `source_url` | TEXT | Nullable. Originating URL. |
| `search_filters` | JSONB | Nullable. Keywords used to discover the job (auto-scraping). |
| `match_score` | INTEGER | Nullable. Gemini compatibility score, 0–100. |
| `scored_by_resume_id` | UUID | Nullable. FK → `resumes.id` (SET NULL on delete). Resume that produced the score. |
| `score_details` | JSONB | Nullable. `{ rationale, matched_skills, missing_skills }` from Gemini. |
| `status` | VARCHAR(50) | `not_applied` · `applied` · `auto_rejected` · `user_rejected` · `assessment_task` · `assessment_rejected` · `home_test` · `home_test_rejected` · `professional_interview` · `professional_interview_rejected` · `hr_interview` · `hr_interview_rejected` · `accepted`. |
| `is_duplicate` | BOOLEAN | True when near-identical content was already imported. |
| `duplicate_chance` | INTEGER | Nullable. 0–100 duplicate probability from TF-IDF similarity. |
| `published_at` | TIMESTAMPTZ | Nullable. Job posting date extracted from content. |
| `created_at` | TIMESTAMPTZ | DB insertion time. |

### Table: `resumes`

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Primary key. |
| `version_name` | VARCHAR(255) | Human-friendly label, e.g. `"Fullstack React/Python"`. |
| `target_role` | VARCHAR(255) | Nullable. Role this CV targets. |
| `structured_data` | JSONB | Nullable. Ollama-parsed fields (skills, links, experience, etc.). Sent to Gemini for scoring. |
| `raw_text` | TEXT | Full text extracted from the uploaded file. |
| `file_path` | TEXT | Absolute path to the stored PDF/DOCX file on disk. |
| `is_active` | BOOLEAN | At most one resume is active at a time (enforced in application logic, not by DB constraint). |
| `created_at` | TIMESTAMPTZ | Upload time. |

### Table: `settings`

Singleton row. A `CHECK (id = 1)` constraint ensures only one row ever exists; all reads and writes use upsert.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | SMALLINT | Primary key, always `1`. |
| `data` | JSONB | All user settings: `{ blacklist: string[], blacklist_bypass_preference: "ask" \| "always" \| "never" }`. |

### Table: `applications` _(planned)_

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Primary key. |
| `job_id` | UUID | FK → `jobs.id`. |
| `resume_id` | UUID | FK → `resumes.id`. The specific CV used. |
| `applied_at` | TIMESTAMPTZ | Submission time. |
| `application_method` | VARCHAR(255) | e.g. `'Company Website'`, `'Email'`. |
| `cover_letter_text` | TEXT | Nullable. Generated cover letter. |

## 6. API ENDPOINTS

All routes are prefixed with `/api`.

### Jobs

| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/jobs/scrape` | Run the full ingestion + scoring pipeline for one job (URL or raw text). Returns HTTP 201 on fresh score, 200 on cache hit, 422 on blacklist/classification, 400 on no active resume. |
| `GET` | `/jobs/{job_id}/cached-score` | Read-only cache check for a `(job, resume)` pair — no DB writes, no Gemini calls. Query param: `resume_id`. |

### Resumes

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/resumes` | List all resumes, newest first. Supports `limit` / `offset` pagination. |
| `POST` | `/resumes/upload` | Upload a PDF or DOCX resume. Extracts text, parses structured data with Ollama, and persists the record. |
| `GET` | `/resumes/{resume_id}` | Fetch a single resume including full `structured_data`. |
| `PUT` | `/resumes/{resume_id}` | Update `version_name` and/or `structured_data`. |
| `GET` | `/resumes/active` | Return the currently active resume. HTTP 404 when none is active. |
| `PUT` | `/resumes/{resume_id}/set-active` | Mark a resume as active; clears `is_active` on all others. |

### Settings

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/settings/blacklist` | Return the current keyword blacklist. |
| `POST` | `/settings/blacklist` | Add a keyword. HTTP 409 on duplicate, 422 if blank. |
| `DELETE` | `/settings/blacklist/{keyword}` | Remove a keyword (no-op if absent). |
| `GET` | `/settings/blacklist-bypass-preference` | Return the stored bypass preference (`ask` / `always` / `never`). |
| `PUT` | `/settings/blacklist-bypass-preference` | Persist the bypass preference. |

### Health

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Liveness check. Returns `{ status: "ok" }`. |
