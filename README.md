# Zync 🎯

> **Zync** is an AI-driven, hyper-personalized job hunting and application management automation system. It acts as an autonomous agent that scrapes job postings, deeply analyzes them against your CV using local and cloud LLMs, and helps you apply with pinpoint accuracy.

## 🚀 Vision
Stop sending generic CVs into the void. Zync scans multiple job platforms, evaluates the exact requirements using AI, scores the match, and natively prepares tailored applications. It's built as a lightweight, lightning-fast Desktop application.

## 🛠️ Tech Stack
- **Frontend / UI:** React + TypeScript (Vite), encapsulated as a native desktop app using **Tauri** (Rust).
- **Backend Core:** Python 3.12+ (FastAPI).
- **Database:** PostgreSQL 18 + `asyncpg` + SQLAlchemy (Heavily utilizing `JSONB` for unstructured data).
- **AI Inference Engine:**
  - **Local:** `Ollama` (`llama3:8b`) for cost-free data parsing and sanitization.
  - **Cloud:** `Gemini 1.5 Pro` API for deep reasoning, match scoring, and CV rewriting.
- **Scraping:** BeautifulSoup4 & Playwright.

## 📂 Project Structure
```text
Zync/
├── server/            # Python FastAPI, Scrapers, and AI logic
├── client/            # React App and Tauri configuration
├── DESIGN.md          # Core architecture and Database schemas
├── docker-compose.yml # PostgreSQL infrastructure
└── README.md
```

## ⚙️ Getting Started (Development)

### Prerequisites
1. **Node.js** (v20+)
2. **Python** (3.12+)
3. **Docker Desktop** (running)
4. **Ollama** installed locally with the `llama3:8b` model pulled.
5. Rust & Cargo (for Tauri desktop compilation).

### Step 1: Start the Database Infrastructure
Zync requires a PostgreSQL instance. We provide a Docker setup for the DB.
```bash
docker compose up -d
```
*Note: Connect to `localhost:5432` using your preferred DB client (e.g., DBeaver, VSCode extension).*

### Step 2: Setup the Server
*(Coming soon: FastAPI setup instructions)*

### Step 3: Setup the Client
*(Coming soon: React/Tauri setup instructions)*

## 🛡️ Privacy First
Zync is designed to process highly sensitive personal data (resumes, emails, job histories). 
- All standard processing is done **locally** via Ollama. 
- Only explicitly approved payloads are sent to the Gemini API.
- Your data never leaves your local PostgreSQL database.
