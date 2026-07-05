# build_plan.md — ToxiScan Build Plan

> Based on SPEC.md, CLAUDE.md, and decisions.md | Updated: July 2026
> Priority order follows SPEC.md §Build Priority

---

## Overview

ToxiScan is built in **10 phases**. Each phase has a clear goal, deliverables, and done-criteria.
Do not move to next phase until current phase's done-criteria are fully met.

---

## Phase 1 — MongoDB Setup

**Goal:** Create the chemicals collection schema + seed it with real sample data.

**Tasks:**
- Create MongoDB Atlas free cluster (M0)
- Create `toxiscan` database
- Create `chemicals` collection with schema from SPEC.md
- Seed 15-20 real harmful chemicals (Formaldehyde, Parabens, SLS, Fragrance, Phthalates, etc.)
- Create `scan_logs` collection (empty, schema ready)
- Enable connection pooling settings (max 10 connections for M0 free tier)

**Deliverables:**
- MongoDB Atlas cluster live
- `chemicals` collection with 15+ seed documents
- `MONGODB_URI` connection string ready for `.env`

**Done criteria:**
- Can query chemicals via Atlas UI
- At least 5 High severity, 5 Medium, 5 Low chemicals seeded
- Schema matches SPEC.md exactly

---

## Phase 2 — FastAPI Backend Skeleton

**Goal:** Working FastAPI app with health check + MongoDB connection + env config.

**Tasks:**
- `cd backend && pip install fastapi uvicorn motor python-dotenv pydantic`
- Create `main.py` with FastAPI app, CORS config (localhost:3000 + Vercel domain)
- Create `.env` file with all secrets (add to `.gitignore` immediately)
- Create `services/db.py` — motor async MongoDB connection with connection pooling
- Create `models/schemas.py` — Pydantic request/response models
- Create `GET /health` endpoint → `{"status": "ok"}`

**Deliverables:**
- `backend/main.py`
- `backend/services/db.py`
- `backend/models/schemas.py`
- `backend/.env` (gitignored)
- `backend/requirements.txt`

**Done criteria:**
- `uvicorn main:app --reload` starts without error
- `GET /health` returns `{"status": "ok"}`
- MongoDB connection confirmed via db.py connection test log

---

## Phase 3 — Text Analysis Endpoint (No AI)

**Goal:** `POST /analyze/text` working with hardcoded ingredient matching against MongoDB.

**Tasks:**
- Create `routers/analyze.py`
- Install `rapidfuzz` — `pip install rapidfuzz`
- Create `services/scoring.py` — pure Python safety score formula from SPEC.md
- Implement fuzzy matching logic (85% threshold via rapidfuzz)
- `POST /analyze/text` accepts `{"ingredients": "string"}`, returns full response schema
- Hardcode ingredient parsing (simple comma split) — no AI model yet
- Async log write to `scan_logs` collection (BackgroundTasks, fire-and-forget)

**Deliverables:**
- `backend/routers/analyze.py`
- `backend/services/scoring.py`

**Done criteria:**
- POST `/analyze/text` with `"sodium lauryl sulfate, water, fragrance"` returns correct chemicals flagged
- Safety score calculates correctly (test with known High/Medium/Low chemical combo)
- Score caps at 0, never goes negative
- Scan log written async to MongoDB

**Score formula test case:**
```
Input: 1 High + 1 Medium chemical
Expected score: 10 - 2.5 - 1.5 = 6.0 → CAUTION verdict
```

---

## Phase 4 — NaraRouter Text Model Integration

**Goal:** Replace hardcoded comma-split parsing with NaraRouter text model for intelligent ingredient normalization.

**Tasks:**
- `pip install openai` (used with custom base_url for NaraRouter)
- Create `services/text_model.py`
- Configure openai client: `base_url="https://router.bynara.id/v1"`, `api_key=NARA_ROUTER_API_KEY`
- Prompt: extract and normalize ingredient list from raw user text (handle INCI names, misspellings)
- Model returns clean list → feeds into existing fuzzy matching pipeline
- Add `TEXT_MODEL` env var (e.g., `deepseek-r1` or check NaraRouter `/v1/models`)
- Handle NaraRouter token quota error gracefully (try-except, return 503 with message)

**Deliverables:**
- `backend/services/text_model.py`

**Done criteria:**
- Messy input `"aqua, sodium laureth sulphate, parfum, methylparaben"` → correctly normalized and matched
- INCI name `"parfum"` recognized as `"Fragrance"` in DB
- NaraRouter API errors handled, not exposed to frontend

---

## Phase 5 — NaraRouter Vision Model Integration

**Goal:** `POST /analyze/image` endpoint — image → ingredient extraction.

**Tasks:**
- Create `services/vision.py`
- Hit `GET /v1/models` on NaraRouter → find correct Groq vision model alias → set `VISION_MODEL` in `.env`
- Accept multipart/form-data image upload (max 10MB)
- Convert image to base64 → send to vision model via NaraRouter
- Extract: product name, brand, full ingredient list from image
- Feed extracted ingredients into same pipeline as text path
- Handle blurry/unreadable image → return `{"error": "Could not read ingredients from image. Please try text input."}`
- Image NEVER saved to disk — process in memory only

**Deliverables:**
- `backend/services/vision.py`
- `backend/routers/analyze.py` updated with `/analyze/image` route

**Done criteria:**
- Upload clear product image → ingredients extracted correctly
- Upload blurry image → friendly error message returned, no crash
- Verified: no image file written to disk at any point
- When both image + text provided → image path used, text ignored

---

## Phase 6 — Tavily Web Search Integration

**Goal:** Auto-fetch research URLs for chemicals missing them in DB.

**Tasks:**
- `pip install tavily-python`
- Create `services/search.py`
- Logic: after DB lookup, check which matched chemicals have `research_url == null`
- For each such chemical (max 5): call Tavily with query `"[chemical_name] cancer carcinogen cosmetic research study"`
- Use top 1 result URL as temporary research_url in response (NOT saved to DB)
- If Tavily returns nothing → set research_url to null, no error shown to user
- Add request-level counter — stop at 5 Tavily calls regardless of how many chemicals need it
- Log Tavily usage count to console (for monitoring free tier: 1,000/month)

**Deliverables:**
- `backend/services/search.py`

**Done criteria:**
- Chemical with no research_url → Tavily result URL appears in API response
- Max 5 Tavily calls per request enforced (test with 8+ chemicals missing URLs)
- Tavily failure → graceful null, no 500 error

---

## Phase 7 — Safety Scoring Logic (Finalize)

**Goal:** Verify and harden scoring.py with edge cases.

**Tasks:**
- Unit test scoring formula with all edge cases:
  - All safe ingredients → score 10, SAFE
  - Single High chemical → score 7.5, CAUTION
  - 5 High chemicals → score 0, AVOID (capped, not negative)
  - Mix of severities → correct math
- Verify verdict thresholds match SPEC.md exactly (8-10 SAFE, 5-7.9 CAUTION, 0-4.9 AVOID)
- Add type hints to all scoring functions

**Deliverables:**
- `backend/services/scoring.py` (finalized)
- `backend/tests/test_scoring.py`

**Done criteria:**
- All edge case tests pass
- Score never goes below 0 or above 10
- Python type hints on all functions

---

## Phase 8 — Next.js Frontend

**Goal:** Full UI — upload form + results display.

**Tasks:**
- `cd frontend && npx create-next-app@14 . --typescript --tailwind --app`
- Create components:
  - `UploadForm` — image upload + text textarea, validation, submit
  - `ResultCard` — top-level result container
  - `ChemicalCard` — individual harmful chemical with all fields
  - `ScoreGauge` — visual 0-10 meter (SVG or CSS)
  - `Verdict` — SAFE/CAUTION/AVOID with color
- All components: handle loading / error / empty / success states
- Image upload: preview before submit
- `NEXT_PUBLIC_API_URL` env var for backend URL
- Cold start detection: if backend takes >5s, show "Waking up server..." message
- "Check Another Product" button resets form
- Mobile responsive (test at 375px width)

**Deliverables:**
- `frontend/app/page.tsx`
- `frontend/components/` — all 5 components

**Done criteria:**
- Full flow works end-to-end in browser
- No API keys visible in browser devtools Network tab or Sources
- Loading, error, empty, success states all render correctly
- Works on mobile (375px viewport)

---

## Phase 9 — Polish

**Goal:** Edge cases, UX improvements, error handling.

**Tasks:**
- "No harmful chemicals detected" empty state (show green checkmark)
- Research URL → opens in new tab
- Collapsible "All Ingredients" section
- Detected product name shown at top
- Validate file type + size (10MB limit) on frontend before upload
- Error boundary for React errors
- Run `npm run lint` — fix all warnings
- Check all Python files for type errors

**Done criteria:**
- `npm run lint` passes with zero errors
- No Python runtime errors on any valid input
- All 5 async states handled in every component

---

## Phase 10 — Deploy

**Goal:** Live on Vercel + Render.

**Tasks:**
- Push code to GitHub (confirm `.env` is NOT committed)
- Deploy backend to Render (free tier, Python environment)
  - Set all env vars in Render dashboard
  - Note: cold start after 15min inactivity — handled by frontend message
- Deploy frontend to Vercel
  - Set `NEXT_PUBLIC_API_URL` to Render backend URL
- Test full flow on production URLs
- Confirm no API keys in Vercel build output

**Done criteria:**
- Both URLs live and working
- Image upload → results within 10 seconds
- Text input → results within 5 seconds
- API keys not visible in any frontend bundle

---

## Quick Reference — Phase Status

| Phase | What | Status |
|-------|------|--------|
| 1 | MongoDB Setup | ⬜ TODO |
| 2 | FastAPI Skeleton | ⬜ TODO |
| 3 | Text Endpoint (No AI) | ⬜ TODO |
| 4 | NaraRouter Text Model | ⬜ TODO |
| 5 | Vision Model + Image Endpoint | ⬜ TODO |
| 6 | Tavily Web Search | ✅ DONE |
| 7 | Scoring Finalize + Tests | ✅ DONE |
| 8 | Next.js Frontend | ✅ DONE |
| 9 | Polish | ⬜ TODO |
| 10 | Deploy | ⬜ TODO |

> Update status: ⬜ TODO → 🔄 IN PROGRESS → ✅ DONE