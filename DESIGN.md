# ZYNC - SYSTEM DESIGN DOCUMENT

## 1. SYSTEM OVERVIEW
Zync is an automated, AI-driven job hunting and application management system. It scrapes job listings, parses user CVs, evaluates match scores using LLMs (Local and API-based), and manages the application lifecycle.

## 2. ARCHITECTURE DIAGRAM
The system follows a modern desktop-web architecture:
- **Presentation Layer (Tauri + React):** A lightweight desktop application. React (TypeScript, Vite) handles the UI/UX, while Tauri (Rust) provides the native OS shell.
- **Backend Layer (FastAPI):** A Python 3.12+ async server. Handles scraping logic, business rules, and API endpoints for the frontend.
- **AI Processing Layer:**
  - `Ollama (llama3:8b)`: Local inference for lightweight tasks (data extraction, sanitization, simple parsing) to save costs.
  - `Gemini 1.5 Pro (API)`: Cloud inference for complex reasoning (Match Scoring, CV tailoring, Cover Letter generation).
- **Data Layer (PostgreSQL):** Stores jobs, resumes, and user settings. Uses `asyncpg` driven by `SQLAlchemy` (ORM) for async DB operations. Heavily utilizes `JSONB` for unstructured metadata.

## 3. CORE WORKFLOWS
### 3.1. Job Discovery (The Trigger)
1. **Manual Entry:** User pastes a URL. Backend validates and extracts raw HTML.
2. **Auto-Scraping:** Backend runs scheduled jobs to scrape predefined sources (LinkedIn, Glassdoor, etc.).
3. **Parsing:** HTML is passed to Ollama/Gemini to extract structured fields (Company, Title, Requirements).

### 3.2. Evaluation (The Brain)
1. Backend retrieves the user's active Resume (`raw_text` and `structured_data`).
2. Gemini evaluates the Job Requirements against the Resume.
3. Generates a `match_score` (0-100) and rationale.
4. Identifies potential duplicates using embeddings or text-similarity against existing DB entries.

### 3.3. Action & Management
1. High-match jobs trigger local push notifications (via Tauri).
2. Users can view jobs in the Dashboard.
3. [Future Beta] One-click customized CV generation and semi-auto application.

## 4. DATABASE SCHEMA (PostgreSQL)

### Table: `jobs`
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Primary Key |
| `company_name` | VARCHAR(255) | Nullable. Extracted company name. |
| `job_title` | VARCHAR(255) | Nullable. Extracted job title. |
| `company_description` | TEXT | Nullable. |
| `job_description` | TEXT | Nullable. |
| `requirements` | JSONB | Nullable. Extracted constraints (years, stack). |
| `source_type` | VARCHAR(50) | 'manual' or 'auto' |
| `source_url` | TEXT | Nullable. Link to the job post. |
| `search_filters` | JSONB | Nullable. Keywords used to find the job. |
| `match_score` | INTEGER | Nullable. 0-100 compatibility score. |
| `status` | VARCHAR(50) | 'not_applied', 'applied', 'auto_rejected', 'user_rejected', 'assessment_task', 'assessment_rejected', 'home_test', 'home_test_rejected', 'professional_interview', 'professional_interview_rejected', 'hr_interview', 'hr_interview_rejected', 'accepted' |
| `is_duplicate` | BOOLEAN | Flag for identical jobs. |
| `duplicate_chance` | INTEGER | 0-100 probability of being a duplicate. |
| `published_at` | TIMESTAMP | Nullable. Job posting date. |
| `created_at` | TIMESTAMP | DB insertion time. |

### Table: `resumes`
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Primary Key |
| `version_name` | VARCHAR(255) | e.g., "Fullstack React/Python" |
| `target_role` | VARCHAR(255) | Nullable. Role this CV targets. |
| `structured_data` | JSONB | Nullable. AI-parsed fields (skills, links). |
| `raw_text` | TEXT | Full text extracted from file. |
| `file_path` | TEXT | Local system path to the original PDF/Doc. |
| `created_at` | TIMESTAMP | Upload time. |

### Table: `applications`
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Primary Key |
| `job_id` | UUID | FK -> `jobs.id` |
| `resume_id` | UUID | FK -> `resumes.id`. The specific CV used. |
| `applied_at` | TIMESTAMP | Submission time. |
| `application_method` | VARCHAR(255) | e.g., 'Company Website', 'Email'. |
| `cover_letter_text`| TEXT | Nullable. Generated cover letter. |

## 5. API ENDPOINTS (Draft)
- `POST /api/jobs/scrape` - Trigger manual URL scrape.
- `GET /api/jobs` - Fetch jobs with filters (Dashboard view).
- `POST /api/resumes/upload` - Upload and parse a new CV.
- `POST /api/evaluate/{job_id}` - Force match-score calculation.
