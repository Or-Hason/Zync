# Zync 🎯

> **Zync** is an AI-driven, hyper-personalized job hunting and application management automation system. It acts as an autonomous agent that scrapes job postings, deeply analyzes them against your CV using local and cloud LLMs, scores the match, and helps you apply with pinpoint accuracy.

## 🚀 Vision
Stop sending generic CVs into the void. Zync scans multiple job platforms, evaluates the exact requirements using AI, scores the match, and natively prepares tailored applications — all from a lightweight, lightning-fast desktop application.

## 🛠️ Tech Stack
- **Frontend / UI:** React + TypeScript (Vite), packaged as a native desktop app via **Tauri** (Rust).
- **Backend:** Python 3.12+ (FastAPI, fully async).
- **Database:** PostgreSQL 18 + `asyncpg` + SQLAlchemy 2.0 (Alembic migrations, JSONB-heavy schema).
- **AI Inference:**
  - **Local:** `Ollama` (`llama3:8b`) for cost-free job parsing, resume extraction, and content classification.
  - **Cloud:** `Gemini Flash` API for deep reasoning — match scoring, skill gap analysis, and CV rewriting.
- **Similarity Engine:** `scikit-learn` TF-IDF cosine similarity for duplicate detection and score caching.
- **Scraping:** BeautifulSoup4 (HTML extraction); Playwright _(planned)_.
- **Resume Parsing:** `pdfminer.six` (PDF), `python-docx` (DOCX).
- **Date Parsing:** `dateparser` for normalizing relative and locale-aware date strings extracted from job postings.

## 📂 Project Structure
```text
Zync/
├── server/            # Python FastAPI server, AI services, scrapers
│   ├── app/
│   │   ├── api/       # Route handlers and pipeline helpers
│   │   ├── models/    # SQLAlchemy ORM models
│   │   ├── schemas/   # Pydantic request/response schemas
│   │   └── services/  # Business logic (scoring, parsing, caching, etc.)
│   ├── alembic/       # Database migration scripts
│   └── tests/
├── client/            # React + Tauri desktop application
│   ├── src/           # TypeScript / React source
│   └── src-tauri/     # Tauri (Rust) native shell
├── DESIGN.md          # Architecture, database schema, API reference
├── docker-compose.yml # PostgreSQL infrastructure
└── README.md
```

## ⚙️ Getting Started (Development)

### Prerequisites
1. **Node.js** v20+
2. **Python** 3.12+
3. **Rust & Cargo** (required by Tauri — install via [rustup](https://rustup.rs))
4. **Docker Desktop** (running, for PostgreSQL)
5. **Ollama** installed locally with the `llama3:8b` model pulled (`ollama pull llama3:8b`)
6. A **Gemini API key** (required for match scoring — [get one here](https://aistudio.google.com/apikey))

---

### Step 1: Start the Database

```bash
docker compose up -d
```

This starts a PostgreSQL 18 instance on `localhost:5432` with the default credentials in `docker-compose.yml`.

---

### Step 2: Set Up the Server

```bash
cd server
```

**Create a `.env` file** in the `server/` directory with at minimum:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

All other settings have sensible defaults (see `app/core/config.py`). Override as needed:
```env
# Database (defaults match docker-compose.yml)
DB_HOST=localhost
DB_PORT=5432
DB_USER=zync_user
DB_PASSWORD=zync_password
DB_NAME=zync_db

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:8b

# Gemini (required for scoring)
GEMINI_API_KEY=your_gemini_api_key_here
```

**Install dependencies:**
```bash
pip install -e .
```

**Run database migrations:**
```bash
alembic upgrade head
```

**Start the server:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

### Step 3: Set Up the Client

```bash
cd client
npm install
```

**Run in browser (dev mode, no Tauri shell):**
```bash
npm run dev
```

**Run as a native desktop app:**
```bash
npm run tauri dev
```

---

## 🛡️ Privacy First
Zync processes highly sensitive personal data (resumes, job histories).
- All standard processing runs **locally** via Ollama — parsing, classification, and duplicate detection never touch external servers.
- Only the minimum required payload (job requirements + resume structured data) is sent to the Gemini API for scoring.
- Raw resume text, PII fields, and API keys are never written to logs.
- Your data stays in your local PostgreSQL database.
