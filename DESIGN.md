# ZYNC - SYSTEM DESIGN DOCUMENT

## 1. SYSTEM OVERVIEW
Zync is an automated, AI-driven job hunting and application management system. It scrapes job listings, parses user CVs, evaluates match scores using LLMs (local and cloud), filters noise via a keyword blacklist, and manages the application lifecycle through a React + Tauri desktop application.

## 2. ARCHITECTURE

The system follows a modern desktop-web architecture:

- **Presentation Layer (Tauri + React):** A lightweight desktop application. React (TypeScript, Vite) handles the UI/UX; Tauri (Rust) provides the native OS shell and inter-process bridge.
- **Server Layer (FastAPI):** A Python 3.12+ async server handling scraping logic, business rules, and REST API endpoints. All I/O-bound operations are fully async (`asyncpg`, `httpx`, `aiofiles`).
- **AI Processing Layer:**
  - `Ollama (llama3:8b)`: Local inference for lightweight tasks — job content extraction, content classification, resume parsing. Zero API cost; data stays local.
  - `Gemini Flash (API)`: Cloud inference for complex reasoning — match scoring (0–100), rationale generation, skill gap analysis, cover letter tailoring, _(Planned)_ CV tailoring.
- **Data Layer (PostgreSQL 18):** Stores jobs, resumes, and user settings. Uses `asyncpg` driven by SQLAlchemy 2.0 (async ORM) with Alembic for schema migrations. Heavily utilizes `JSONB` for dynamic metadata (requirements, score details, settings).

## 3. AI RESPONSIBILITY ARCHITECTURE

A strict boundary separates the two AI layers to keep prompts simple, costs predictable, and behaviour deterministic:

| Concern | Ollama (local) | Gemini (cloud) |
| :--- | :--- | :--- |
| **Role** | Dumb extraction — pull structured fields from raw text | Smart reasoning — evaluate, compare, score |
| **Tasks** | Job field extraction (title, company, dates, requirements, application options), resume parsing, content classification | Match scoring (0–100), rationale generation, skill gap analysis, cover letter tailoring |
| **Prompt style** | Short, strict, schema-bound. Outputs are sanitized and length-capped before use. | Rich context (requirements JSONB + resume structured data). Output is validated against a Pydantic schema. |
| **Data sent** | Raw job posting or resume text (local inference — never leaves the machine) | Only `{ job_title, job_description, requirements, structured_resume_data }` — PII fields stripped before dispatch |
| **Failure mode** | Up to 3 retry attempts on empty parse; job silently dropped (not persisted) if all retries fail | Scoring returns `null` on failure; the job is still persisted without a score |

**Rule:** Ollama prompts must never perform reasoning or ranking. Gemini prompts must never perform raw text extraction. Mixing these responsibilities is a regression.

### Gemini Reliability — Stateful Model Rotation

`GEMINI_MODELS` (comma-separated env var) defines an ordered fallback list. A module-level `current_model_index` and `last_rotated_at` singleton govern rotation:

- **Permanent errors** (non-429 `ClientError`, e.g. 400, 403): re-raised immediately, no rotation.
- **Quota exhaustion** (429 with `"quota"` / `"exhausted"` in message): rotates to the next model immediately.
- **Transient errors** (soft 429 or any `ServerError` / 5xx): retries the same model up to 3× with 2 s → 4 s exponential back-off, then rotates.
- **Full exhaustion**: all models tried → raises `GeminiUnavailableError` → HTTP 503.
- **1-hour reset**: if `datetime.now() - last_rotated_at >= 1 hour`, index resets to 0 (primary) before the next call.

Scoring domain helpers (prompt building, PII stripping, response parsing) live in `gemini_scoring.py`; retry/rotation logic lives in `gemini_client.py`.

## 4. CORE WORKFLOWS

### 4.1 Job Discovery

1. **Manual Entry:** User pastes a URL or raw job text. The server fetches the HTML (URL path), extracts readable content with BeautifulSoup4, and enforces a content size cap.
2. **Auto-Scraping:** An `APScheduler AsyncIOScheduler` fires every 5 minutes (base tick). On each tick it re-reads `auto_scan_enabled` and `scan_frequency_hours` from the DB; the scan only runs when due (elapsed ≥ frequency − 5 min slack). The JobMaster scraper (`server/app/scraper/jobmaster.py`) reads `target_role` from the active resume's `structured_data`, deduplicates against existing `source_url` values, caps the first run to `INITIAL_SCAN_LIMIT` jobs, and populates `search_filters` JSONB on every saved row. A **Scan Now** button triggers an immediate manual scan via `POST /api/settings/scan/trigger` (runs in a background task; guarded by a `scan_in_progress` flag to prevent double-runs).
3. **Parsing:** Extracted text is passed to Ollama to produce structured fields (company, title, description, requirements, application options, classification, published date). Ollama retries up to 3× on empty response; a persistent failure drops the job without a DB write.

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

### 4.3 Notifications

Push notifications fire immediately after the background scraper (or manual scan) scores a job at or above the user's `notification_score_threshold`:

- **Backend:** After scoring, the pipeline calls `notification_bus.emit_job_match(job_id, job_title, match_score)`. A `notified_at` timestamp is written to the `jobs` row; subsequent ticks skip re-notification for the same job. `GET /api/notifications/stream` is a long-lived Server-Sent Events endpoint that fans events out via per-client `asyncio.Queue`. Comment-line pings fire every 30 s to prevent proxy timeouts.
- **Frontend:** `useNotifications` hook (mounted once in `App.tsx`) opens an `EventSource` to `/api/notifications/stream`. On `job_match` events it calls `fireNotification(jobTitle, matchScore)`.
  - **Tauri (Windows):** a custom `show_toast` Rust command (`src-tauri/src/notification.rs`) drives `tauri-winrt-notification`'s `Toast::on_activated`. On click, Rust restores the window (`unminimize → show → set_focus`) and emits `notification://activated`; the frontend listener then runs the pending navigation.

    The bundled `tauri-plugin-notification` is **not** used for this: its Actions API is mobile-only, and no desktop code path emits the `actionPerformed` event that `onAction()` subscribes to, so a clicked toast can only dismiss. The toast is built on the main thread because it owns the STA message pump WebView2 requires, and WinRT dispatches activation through it. Unpackaged builds fall back to `Toast::POWERSHELL_APP_ID`, since Windows renders a toast only under a registered AppUserModelID.
  - **Tauri (macOS / Linux):** falls back to `tauri-plugin-notification`. The notification appears but the click is inert — an upstream gap, tracked separately.
  - **Web:** `new Notification(title, { body })`. `onclick` calls `e.preventDefault() → notif.close() → window.focus()`. Permission is requested lazily on first event; a dismissible banner renders when permission is `"denied"`.

**Click routing.** A multi-job notification navigates to `/explorer?is_new=true&is_unread=true`. The Explorer *replaces* its filter state rather than merging — intersecting with the user's existing filters routinely yields an empty grid — and force-opens the filter panel so the two active filters that explain the result are visible.

### 4.4 Action & Management

1. Users view and manage scored jobs in the **Job Explorer** — a sortable data grid with faceted filters (role, company, score, date range, CV, source, skills, experience) plus free-text search. Unread and new-in-24h rows are visually marked; opening a job stamps `viewed_at`.
2. The active resume can be switched at any time; the frontend performs a read-only cache check to show the cached score for the selected resume without re-scoring.
3. Each job card displays a **View Original Job** button (when `source_url` is present), `recommended_apply_method`, and a **Ways to Apply** section (when `application_options.length > 1`).
4. **Cover letters** are generated on demand per `(job, CV)` pair from a user-supplied template, tailored by Gemini, and reviewed in a side-by-side diff editor before use.
5. _(Planned)_ One-click tailored CV generation and semi-auto application submission.

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
| `status` | VARCHAR(50) | `not_applied` · `applied` · `auto_rejected` · `user_rejected` · `assessment_task` · `assessment_rejected` · `home_test` · `home_test_rejected` · `professional_interview` · `professional_interview_rejected` · `hr_interview` · `hr_interview_rejected` · `accepted`. |
| `application_options` | JSONB | Nullable. List of extracted email addresses or external ATS URLs from the job text. |
| `recommended_apply_method` | TEXT | Preferred application channel extracted by Ollama. Defaults to `"Apply via the platform's native button"`. |
| `is_duplicate` | BOOLEAN | True when near-identical content was already imported. |
| `duplicate_chance` | INTEGER | Nullable. 0–100 duplicate probability from TF-IDF similarity. |
| `notified_at` | TIMESTAMPTZ | Nullable. Set when a push notification was emitted; prevents duplicate notifications on subsequent scraper ticks. |
| `viewed_at` | TIMESTAMPTZ | Nullable. Stamped when the user first opens the job. `NULL` drives the Explorer's *Unread* filter and row highlight. |
| `published_at` | TIMESTAMPTZ | Nullable. Job posting date extracted from content. |
| `created_at` | TIMESTAMPTZ | DB insertion time. Also drives the *New (24h)* filter. |

### Table: `job_scores`

Bridging table between `jobs` and `resumes`: **one row per (job, CV) pair**. Scoring a job with a second CV adds a row here — the job row is never duplicated. A re-score with a CV that already scored the job is an UPSERT on the unique constraint.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Primary key. |
| `job_id` | UUID | FK → `jobs.id` (CASCADE on delete). |
| `resume_id` | UUID | FK → `resumes.id` (CASCADE on delete). Deleting a CV removes its scores; the jobs survive. |
| `match_score` | INTEGER | Gemini compatibility score, 0–100. Not nullable — an unscored job simply has no row. |
| `score_details` | JSONB | Nullable. `{ rationale, matched_skills, missing_skills }` from Gemini. |
| `created_at` | TIMESTAMPTZ | First score time. |
| `updated_at` | TIMESTAMPTZ | Last re-score time. |

`UNIQUE (job_id, resume_id)` — a given CV holds at most one score per job.

**Score selection (single source of truth):** endpoints and the Explorer grid both resolve "which score represents this job" the same way — the **Active Resume**'s score if it has one, otherwise the **highest** score. The Explorer's *Show Best Match* toggle overrides step 1 and always takes the highest.

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

### Table: `cover_letters`

One row per `(job, CV)` pair, mirroring `job_scores`. Regenerating for the same pair is an UPSERT on the unique constraint.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Primary key. |
| `job_id` | UUID | FK → `jobs.id` (CASCADE on delete). |
| `resume_id` | UUID | FK → `resumes.id` (CASCADE on delete). |
| `original_template_text` | TEXT | Nullable. The user's template as it was at generation time, retained so the diff view stays meaningful after the stored template changes. |
| `generated_text` | TEXT | The tailored letter. User edits overwrite this. |
| `gemini_summary` | TEXT | Nullable. Short explanation of what was changed and why. |
| `created_at` | TIMESTAMPTZ | Generation time. |

`UNIQUE (job_id, resume_id)`.

### Table: `settings`

Singleton row. A `CHECK (id = 1)` constraint ensures only one row ever exists; all reads and writes use upsert.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | SMALLINT | Primary key, always `1`. |
| `data` | JSONB | All user settings, grouped by concern. Each group is owned by a dedicated store under `app/services/settings/`. |

| Group | Keys |
| :--- | :--- |
| Blacklist | `blacklist: string[]`, `blacklist_bypass_preference: "ask" \| "always" \| "never"` |
| Auto-scan | `auto_scan_enabled: bool`, `scan_frequency_hours: 1\|3\|6\|12\|24`, `notification_score_threshold: 0–100`, `last_scan_at: ISO \| null`, `next_scheduled_scan_at: ISO \| null`, `scan_in_progress: bool` |
| Notifications | `notification_mode: "A"\|"B"\|"C"`, `daily_notify_time: "HH:MM" \| null`, `notify_if_zero: bool`, `dnd_start` / `dnd_end: "HH:MM" \| null`, `immediate_job_threshold: 0–100 \| null`, `immediate_jobs_found_since_reset: int` |
| Cover letters | `letter_template_text: string \| null`, `letter_template_filename: string \| null` |

### Table: `applications` _(schema only — no feature yet)_

Created in migration `0001` and mapped by `app/models/application.py`, but no endpoint reads or writes it. Reserved for application-lifecycle tracking.

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
| `GET` | `/jobs` | Explorer list. Filters: `q`, `date_from`, `date_to`, `min_score`, `role`, `company`, `cv_id`, `source_type`, `has_cover_letter`, `is_new`, `is_unread`, `skills[]`, `min_experience`, `status`. Each row carries a `scores[]` array (one entry per CV that scored it). |
| `GET` | `/jobs/{job_id}` | Full job detail. |
| `GET` | `/jobs/{job_id}/cached-score` | Read-only cache check for a `(job, resume)` pair — no DB writes, no Gemini calls. Query param: `resume_id`. |
| `GET` | `/jobs/skills` | Distinct skill vocabulary across all jobs, for the skills filter. |
| `GET` | `/jobs/facets` | Distinct role and company lists for the Explorer autocompletes. Derived from every job in the DB, not the filtered page. |
| `PATCH` | `/jobs/{job_id}/read` | Stamp `viewed_at`. |
| `PATCH` | `/jobs/read-all` | Stamp `viewed_at` on every unread job. |

**Route order matters:** `/jobs/skills`, `/jobs/facets`, and `/jobs/read-all` are registered before `/jobs/{job_id}`, otherwise the wildcard captures them as IDs.

### Cover Letters

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/jobs/{job_id}/cover-letter` | Fetch the letter for a `(job, CV)` pair. HTTP 404 when none exists. Query param: `resume_id`. |
| `POST` | `/jobs/{job_id}/cover-letter` | Generate (or regenerate) a tailored letter from the stored template via Gemini. |
| `PATCH` | `/jobs/{job_id}/cover-letter` | Persist user edits to `generated_text`. |

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
| `GET` | `/settings/scan` | Return auto-scan config (`auto_scan_enabled`, `scan_frequency_hours`, `notification_score_threshold`, `last_scan_at`, `scan_in_progress`). |
| `PUT` | `/settings/scan` | Persist auto-scan config. HTTP 400 when enabling without an active resume. |
| `POST` | `/settings/scan/trigger` | Trigger an immediate manual scan (background task). HTTP 409 when a scan is already running; 400 when no active resume. Optional body `{ manual_threshold }` overrides the notification score threshold for this run. Returns `{ status: "started" }`. |
| `GET` | `/settings/notifications` | Return notification delivery config (mode, daily digest time, DND window, immediate threshold). |
| `PUT` | `/settings/notifications` | Persist notification delivery config. |
| `GET` | `/settings/letter-template` | Return the stored cover-letter template and its original filename. |
| `PUT` | `/settings/letter-template` | Upload/replace the template from a file. |
| `PATCH` | `/settings/letter-template` | Update the template text inline. |
| `DELETE` | `/settings/letter-template` | Remove the stored template. |

### Notifications

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/notifications/stream` | Long-lived SSE stream. Emits `job_match` events (`job_id`, `job_title`, `match_score`, `job_count`, `silent`); keepalive comment-pings every 30 s. |
| `POST` | `/notifications/mock-backend-scan` | Development aid: emits a synthetic `job_match` event so the delivery path can be exercised without running a real scan. |

### Health

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Liveness check. Returns `{ status: "ok" }`. |
