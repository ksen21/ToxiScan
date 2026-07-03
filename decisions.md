# decisions.md — ToxiScan Architecture Decisions Log

> Every important decision goes here. Update this file during sessions, not after.
> Format: Date | Decision | Reason

---

## July 2026

**[Jul 2026] App name:** ToxiScan
- Reason: Short, memorable, clearly communicates "toxic + scan"

**[Jul 2026] Frontend: Next.js 14 (App Router) + TypeScript + Tailwind**
- Reason: Fast, SEO-friendly, Vercel-native deployment. TypeScript prevents runtime bugs.

**[Jul 2026] Backend: FastAPI (Python)**
- User already has FastAPI experience (Jan Aushadi project). Python ecosystem best for AI/ML libs.

**[Jul 2026] Database: MongoDB Atlas**
- Reason: Chemicals list is document-structured with variable aliases arrays. Schema-flexible.
- Admin updates DB directly via Atlas UI — no admin panel needed in v1.
- Free M0 tier sufficient for v1.

**[Jul 2026] AI Gateway: NaraRouter (`router.bynara.id`)**
- Reason: User's existing API. OpenAI-compatible — use openai Python SDK with custom base_url.
- Vision (image): Groq model via NaraRouter
- Text reasoning: deepseek-3.2 or equivalent text model via NaraRouter

**[Jul 2026] Web Search: Tavily**
- Reason: Best free tier for AI apps (1,000 searches/month free). LLM-native output format.
- Only called when chemical has no research_url in DB — not for every request.
- Alternative considered: Serper.dev (2,500 trial but then paid). Tavily ongoing free tier wins.

**[Jul 2026] Image NOT stored — processed in memory only**
- Reason: Privacy. Users uploading personal product photos should not have data retained.

**[Jul 2026] Safety scoring: Pure Python math, NOT AI-generated**
- Reason: Consistent, auditable, fast. AI scoring would vary per request. Formula in SPEC.md.

**[Jul 2026] Fuzzy matching: rapidfuzz at 85% threshold**
- Reason: Ingredient names vary (INCI vs common names, misspellings). Hard string match would miss too many. 85% catches variants without too many false positives.

**[Jul 2026] Image takes priority when both image + text provided**
- Reason: Image is the ground truth (actual product label). Text input is user convenience fallback.

**[Jul 2026] No login/auth in v1**
- Reason: Friction reduction. App is a utility tool — anonymous use acceptable. Login planned for v2 (saved history feature).

**[Jul 2026] Deploy: Vercel (frontend) + Render (backend)**
- Reason: User's existing setup from Jan Aushadi project. Familiar workflow.
- Render cold start known issue — show "Waking up server..." message on first request.

---

## Phase 1 Decisions (Jul 2026)

**[Jul 2026] Chemicals seed strategy: Full list in seed_chemicals.py, future additions via Atlas UI**
- Reason: Poori 62 chemicals ki list ek baar seed_chemicals.py se MongoDB mein daali.
- Future mein naye chemicals Atlas UI / Compass se directly insert honge — no code change needed.
- chemical_template.json banaya as reference for correct schema when adding new chemicals.
- Alternative considered: CSV import script — rejected kyunki Atlas UI already simple enough hai.

**[Jul 2026] Chemicals schema: category field add kiya**
- Reason: SPEC.md ke original schema mein category nahi tha, lekin add kiya grouping ke liye.
- Filtering by category (e.g. "Paraben", "PFAS") future mein UI mein useful hoga.
- SPEC.md update karna hai: chemicals schema mein `category` field add karo.

**[Jul 2026] MongoDB cluster name: Cluster0ToxiSCAN**
- Atlas M0 free tier, AWS Mumbai (ap-south-1) region — India ke users ke liye low latency.
- Connection string format: `mongodb+srv://KartiekSen:***@cluster0toxiscan.ylghiy5.mongodb.net/toxiscan`

**[Jul 2026] Motor (async) driver chosen over PyMongo (sync)**
- Reason: FastAPI is async-first. Motor = async MongoDB driver, fits perfectly with FastAPI + asyncio.
- Atlas UI mein "PyMongo Asynchronous" select kiya connection string ke liye.

**[Jul 2026] Password special characters issue — noted**
- pymongo.errors.InvalidURI error aaya kyunki password mein special characters the.
- Fix: Atlas se password change karke simple alphanumeric rakha.
- Rule: MongoDB Atlas password mein sirf letters + numbers use karo (no @, #, ! etc.)

**[Jul 2026] Indexes created on chemicals collection**
- Indexes: `name`, `category`, `severity`
- Reason: Fuzzy matching aur filtering ke liye faster queries.

---

## Phase 2 — FastAPI Backend Skeleton (Completed: 2026-07-03)

**What was built:**
- `main.py` — FastAPI app with lifespan startup/shutdown hooks, CORS middleware
- `services/config.py` — Pydantic-settings based config, loads `.env` (MONGODB_URI, GROQ_API_KEY, GEMINI_API_KEY, ALLOWED_ORIGINS)
- `services/db.py` — Motor async MongoDB client with connection pooling (maxPoolSize=10), connects on startup / closes on shutdown, `get_db()` dependency injector
- `models/schemas.py` — Pydantic v2 models: `ChemicalBase`/`ChemicalOut`, `ScanRequest`/`ScanResponse`, `IngredientResult`, `HealthResponse`, plus `SeverityLevel` and `ChemicalCategory` enums
- `routers/health.py` — `GET /health` endpoint, pings DB and reports connection status
- `requirements.txt` — fastapi, uvicorn, motor, pydantic, pydantic-settings, python-dotenv, httpx, Pillow, groq, google-generativeai, slowapi

**Issues found & fixed:**
- Initial `requirements.txt` pinned `pymongo==4.10.1` directly, which conflicted with `motor==3.6.0`'s internal dependency on `pymongo<4.10`. Fix: removed the explicit pymongo pin and let motor manage its own compatible version.
- Dev machine had Python 3.14 installed, which is too new — Pillow and pydantic-core had no prebuilt wheels and failed building from source (missing Rust/zlib toolchain). Fix: installed Python 3.12 side-by-side and recreated the venv with `py -3.12 -m venv venv`.

**Verified:** `uvicorn main:app --reload` runs clean; `/health` returns `{"status":"ok","environment":"development","db_connected":true}`; MongoDB connects successfully on startup (confirmed via logs).

---

## Phase 3 — Text Scan Endpoint (Completed: 2026-07-03)

**What was built:**
- `POST /scan/text` endpoint — accepts raw ingredient list text + optional product name
- `services/scanner.py` — core matching + scoring logic
  - `split_ingredients()` — splits raw text on `,` `;` `/`
  - `match_ingredient()` — exact case-insensitive match against `chemicals.name` and `chemicals.aliases`
  - `calculate_safety_score()` — starts at 100, deducts points per flagged ingredient by severity (low: -5, moderate: -12, high: -22, critical: -35)
- Safety labels: Safe (85+), Moderate (60-84), Risky (35-59), Dangerous (<35)

**Issue found & fixed:**
- DB seed data stores severity as `"Low"/"Medium"/"High"` (mixed case, "Medium" not "moderate") — Pydantic enum validation was failing on exact match.
- Fix: added `normalize_severity()` in scanner.py that maps any casing/wording (medium→moderate, severe→high, etc.) to the canonical `SeverityLevel` enum before returning results.

**Verified:** 67 chemicals confirmed in DB (not 62 as originally estimated) via `list_chemicals.py` utility script. Specific chemical names (e.g. Butylparaben, BHT, Bronopol) matched correctly with score/label calculated as expected.

---

## Phase 4 — Fuzzy/Partial Ingredient Matching (Completed: 2026-07-03)

**Problem:** Product labels often list generic terms ("Parabens", "SLS") rather than the exact specific chemical name stored in the DB (e.g. "Butylparaben"). Exact match alone missed these.

**What was built:**
- Extended `match_ingredient()` in `services/scanner.py` with a fallback fuzzy match, triggered only when exact match fails and ingredient length >= 4 chars:
  - **Case A:** ingredient text contains a DB name/alias as substring (e.g. "Parabens (Butylparaben)")
  - **Case B:** ingredient's singular root (trailing "s" stripped) appears inside a DB name/alias (e.g. "Parabens" → "Paraben" → matches "Butylparaben")

**Known limitation:** When a generic term matches multiple possible chemicals (e.g. "Parabens" could mean any of several parabens in DB), only the first DB match found is returned — not an aggregate of all matching chemicals. Acceptable for MVP; can be revisited if false precision becomes an issue.

**Verified:** Generic terms like "Parabens" and "SLS" now correctly resolve to a specific matched chemical with severity/concerns.

## Future Decisions (TBD)

- [ ] Which specific Groq vision model alias in NaraRouter? (check /v1/models)
- [ ] Which text model alias for ingredient parsing?
- [ ] Scan logs async write strategy (motor background task vs FastAPI BackgroundTasks)
- [ ] SPEC.md update: add `category` field to chemicals schema
- [ ] v2: User accounts + history (likely Supabase Auth or Firebase Auth)
- [ ] v2: Barcode scanning feature



## Phase 5 — Image Scan Endpoint / OCR (Completed: 2026-07-03)

What was built:


services/ocr.py — sends a product label photo to Groq's vision-capable model (meta-llama/llama-4-scout-17b-16e-instruct) with an extraction prompt, returns the raw comma-separated ingredients text. Raises ValueError if no ingredients list is detected in the image.
POST /scan/image in routers/scan.py — accepts a multipart file upload (JPEG/PNG/WebP, max 8MB) + optional product_name form field:

Validates content type and file size
Runs OCR via extract_ingredients_from_image()
Feeds extracted text into the existing scan_ingredients() + calculate_safety_score() pipeline (same logic as /scan/text)
Returns the same ScanResponse shape as the text endpoint





## Design decisions:


Reused the Phase 3/4 matching pipeline entirely — OCR output just becomes the input string, no duplicate scanning logic.
Image encoded as base64 data URL and sent inline in the Groq chat completion request (no separate file storage needed).
Error handling: 400 for bad file type/size, 422 if OCR finds no ingredients, 502 if the OCR API call itself fails.


## Requires: GROQ_API_KEY set in .env (from console.groq.com).

## Status: Verified with a real product label photo — OCR extracted 26 ingredients correctly, 9 flagged (e.g. Mineral Oil matched at moderate severity), safety score/label computed correctly (score 0, "Dangerous").

Additional issues found & fixed during testing:


groq client raised TypeError: AsyncClient.__init__() got an unexpected keyword argument 'proxies' — caused by httpx==0.28.0 removing the proxies kwarg that the installed groq version still passed internally. Fix: pinned httpx==0.27.2 in requirements.txt.
MongoDB connection started failing with SSLV1_ALERT_INTERNAL_ERROR / TLSV1_ALERT_INTERNAL_ERROR across all shard servers (ServerSelectionTimeoutError) after the Python 3.12 venv was recreated. Root cause was environmental (Atlas IP whitelist / antivirus SSL inspection on Windows), not application code — resolved after checking Atlas Network Access and system SSL interception settings. Added certifi.where() as an explicit tlsCAFile in services/db.py as a defensive measure for Windows CA store issues



## Phase 6 — Tavily Web Search Integration (Completed: 2026-07-03)

What was built:


services/search.py — enrich_with_research_urls(results):

Only queries chemicals that are is_flagged=True, have a matched_chemical, and research_url is None.
Query format: "{chemical_name} cancer carcinogen cosmetic research study", max_results=1.
Hard cap: MAX_TAVILY_CALLS_PER_REQUEST = 5, enforced with a running counter — loop breaks the moment the cap is hit, regardless of how many chemicals still need a URL.
tavily-python's TavilyClient is sync-only, so the actual call runs via asyncio.to_thread() to avoid blocking the event loop.
Tavily errors/empty results → caught, logged, research_url stays None — never raised to the route handler.
Results are set only on the in-memory IngredientResult objects for this response — never written back to MongoDB (matches project_rule.md: manual admin decision to add permanent URLs).
Logs "Tavily usage — N call(s) this request" once per request (only if calls were made) for free-tier (1,000/month) monitoring.
If TAVILY_API_KEY isn't set in .env, the client init is skipped and enrichment is a no-op (logged once) — app doesn't crash without a key.



Wired into both POST /scan/text and POST /scan/image in routers/scan.py, called once right after scan_ingredients() and before calculate_safety_score() (score itself is unaffected by research_url).
models/schemas.py — added research_url: Optional[str] = None to IngredientResult.
services/config.py / env.example — added TAVILY_API_KEY.
requirements.txt — added tavily-python==0.5.0.


Bug found & fixed while wiring this up:


services/scanner.py::match_ingredient() was reading doc.get("concerns", []) from MongoDB, but the actual seeded chemical documents use the field name danger_type (see chemical_template.json, seed_chemicals.py) — concerns doesn't exist in the DB at all, so this was always returning [] silently since Phase 3. Fixed to doc.get("danger_type", []). Also added research_url=doc.get("research_url") in the same place, needed for Phase 6 to know which chemicals already have a permanent URL.


Not yet verified live: tavily-python could not be pip-installed or hit in this sandbox (no network access / no TAVILY_API_KEY available here). Logic (5-call cap, skip-if-already-has-url, skip-if-not-flagged, mutate-in-place) was verified with a mocked TavilyClient — all cases pass. TODO next session: run a real /scan/text request locally with a valid TAVILY_API_KEY against a chemical known to have research_url: null in DB (e.g. Imidazolidinyl Urea, Fragrance, Talc — see seed_chemicals.py) and confirm a real URL comes back in the response.

Verified (offline, mocked):


8 flagged chemicals missing research_url → exactly 5 Tavily calls made, 5 enriched, 3 skipped.
Chemical that already has a research_url → left untouched, no Tavily call.
Non-flagged ingredient → left untouched, no Tavily call.
Missing TAVILY_API_KEY → enrichment no-ops cleanly, no crash