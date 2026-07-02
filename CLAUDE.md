# CLAUDE.md — ToxiScan Project Config

> Keep this file under 100 lines. Read this at the start of every session.
> Project: Beauty/cosmetic product ingredient safety checker using AI + harmful chemicals DB.

---

## Project

ToxiScan — Next.js 14 frontend + FastAPI backend. Users upload product images or paste ingredients. AI extracts ingredients, backend cross-checks against MongoDB harmful chemicals database, returns safety score + verdict.

---

## Commands

```bash
# Frontend (Next.js)
cd frontend
npm install
npm run dev          # localhost:3000
npm run build
npm run lint

# Backend (FastAPI)
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000   # localhost:8000

# MongoDB: Use Atlas UI or MongoDB Compass to manage chemicals collection directly
```

---

## Architecture

```
frontend/               → Next.js 14 App Router, TypeScript, Tailwind CSS
  app/page.tsx          → Main single-page UI (upload + results)
  app/api/              → Next.js API routes (ONLY for env var proxying if needed)
  components/           → UploadForm, ResultCard, ChemicalCard, ScoreGauge, Verdict

backend/
  main.py               → FastAPI app entry, CORS config
  routers/
    analyze.py          → POST /analyze/text, POST /analyze/image
  services/
    vision.py           → NaraRouter Groq vision model call
    text_model.py       → NaraRouter text reasoning model call
    db.py               → MongoDB connection + chemicals query
    scoring.py          → Safety score calculation (pure Python, no AI)
    search.py           → Tavily web search (fallback for missing research URLs)
  models/
    schemas.py          → Pydantic request/response models
  .env                  → All secrets here (NEVER commit this)
```

**Data flow:**
User input → FastAPI → NaraRouter API (vision or text) → MongoDB chemicals lookup (fuzzy match) → Tavily (if research_url missing) → Scoring calculation → JSON response → Next.js renders results

---

## API Endpoints

```
POST /analyze/image     → multipart/form-data, field: "image" (file)
POST /analyze/text      → JSON body: { "ingredients": "string" }
GET  /health            → { "status": "ok" }
```

Both analyze endpoints return same response schema (see schemas.py).

---

## Rules

- ALL secrets in `.env` file. NEVER hardcode in any source file.
- `.env` must be in `.gitignore` — check before every git commit.
- NaraRouter base URL: `https://router.bynara.id/v1` — use openai Python SDK with custom base_url.
- Safety scoring ONLY in `services/scoring.py` — never ask AI model to score. Formula is fixed (see SPEC.md).
- Tavily called ONLY when chemical's `research_url` is null in MongoDB. Max 5 Tavily calls per request.
- Images are NEVER stored — process in memory, discard after extraction.
- CORS: allow `http://localhost:3000` (dev) and Vercel domain (prod).
- Fuzzy matching via `rapidfuzz` library, threshold 85% similarity.
- Async log writes to `scan_logs` collection — fire-and-forget, never block response.
- Run `npm run lint` (frontend) and check no Python errors before any git commit.

---

## Forbidden

- Do NOT store uploaded images to disk or any cloud storage
- Do NOT use AI model for safety scoring — scoring.py is pure math
- Do NOT call Tavily more than 5 times per single user request
- Do NOT expose `NARA_ROUTER_API_KEY` or `TAVILY_API_KEY` in frontend code
- Do NOT add login/auth system in v1
- Do NOT add new npm packages without checking if existing ones cover the need
- Do NOT modify MongoDB `chemicals` schema without updating SPEC.md
- Do NOT create duplicate API routes or service functions

---

## Style

- Frontend: Functional components only, no class components. TypeScript strict mode.
- Tailwind only for styling — no CSS modules, no styled-components.
- Every async component must handle: loading state, error state, empty state, success state.
- Backend: Pydantic models for all request/response validation. No raw dicts in route handlers.
- Python type hints on all functions.

---

## Known Sharp Edges

- NaraRouter has per-model-class daily token quota — if one model class hits limit, switch model alias
- Groq vision model name must be verified from `/v1/models` endpoint before hardcoding
- MongoDB Atlas M0 (free) has 512MB storage limit and connection limit of 500 — use connection pooling (motor async driver)
- Render free tier spins down after 15min inactivity — first request may take 30-50s cold start; add loading message "Waking up server..." if cold start detected
- Tavily free tier: 1,000 searches/month — monitor usage, add counter log

---

## Current Focus

> Update this section at the start of each session.

Phase 1: MongoDB setup + FastAPI backend skeleton + text analysis endpoint (no AI yet — hardcode test chemicals).
