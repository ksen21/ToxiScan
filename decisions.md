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

---

## Phase 6 — Tavily Web Search Integration (Completed: 2026-07-03)

**What was built:**
- `services/search.py` — `enrich_with_research_urls(results)`:
  - Only queries chemicals that are `is_flagged=True`, have a `matched_chemical`, and `research_url is None`.
  - Query format: `"{chemical_name} cancer carcinogen cosmetic research study"`, `max_results=1`.
  - Hard cap: `MAX_TAVILY_CALLS_PER_REQUEST = 5`, enforced with a running counter — loop breaks the moment the cap is hit, regardless of how many chemicals still need a URL.
  - `tavily-python`'s `TavilyClient` is sync-only, so the actual call runs via `asyncio.to_thread()` to avoid blocking the event loop.
  - Tavily errors/empty results → caught, logged, `research_url` stays `None` — never raised to the route handler.
  - Results are set only on the in-memory `IngredientResult` objects for this response — never written back to MongoDB (matches project_rule.md: manual admin decision to add permanent URLs).
  - Logs `"Tavily usage — N call(s) this request"` once per request (only if calls were made) for free-tier (1,000/month) monitoring.
  - If `TAVILY_API_KEY` isn't set in `.env`, the client init is skipped and enrichment is a no-op (logged once) — app doesn't crash without a key.
- Wired into both `POST /scan/text` and `POST /scan/image` in `routers/scan.py`, called once right after `scan_ingredients()` and before `calculate_safety_score()` (score itself is unaffected by research_url).
- `models/schemas.py` — added `research_url: Optional[str] = None` to `IngredientResult`.
- `services/config.py` / `env.example` — added `TAVILY_API_KEY`.
- `requirements.txt` — added `tavily-python==0.5.0`.

**Bug found & fixed while wiring this up:**
- `services/scanner.py::match_ingredient()` was reading `doc.get("concerns", [])` from MongoDB, but the actual seeded chemical documents use the field name `danger_type` (see `chemical_template.json`, `seed_chemicals.py`) — `concerns` doesn't exist in the DB at all, so this was always returning `[]` silently since Phase 3. Fixed to `doc.get("danger_type", [])`. Also added `research_url=doc.get("research_url")` in the same place, needed for Phase 6 to know which chemicals already have a permanent URL.

**Not yet verified live:** `tavily-python` could not be pip-installed or hit in this sandbox (no network access / no `TAVILY_API_KEY` available here). Logic (5-call cap, skip-if-already-has-url, skip-if-not-flagged, mutate-in-place) was verified with a mocked `TavilyClient` — all cases pass. **TODO next session:** run a real `/scan/text` request locally with a valid `TAVILY_API_KEY` against a chemical known to have `research_url: null` in DB (e.g. Imidazolidinyl Urea, Fragrance, Talc — see seed_chemicals.py) and confirm a real URL comes back in the response.

**Verified (offline, mocked):**
- 8 flagged chemicals missing `research_url` → exactly 5 Tavily calls made, 5 enriched, 3 skipped.
- Chemical that already has a `research_url` → left untouched, no Tavily call.
- Non-flagged ingredient → left untouched, no Tavily call.
- Missing `TAVILY_API_KEY` → enrichment no-ops cleanly, no crash.

**Live-tested by user (2026-07-05):** `/scan/text` with `Water, Fragrance, Talc, Parabens` — Fragrance and Parabens (matched to Methylparaben) both came back with real `research_url` values (EWG Skin Deep, NCBI PMC article). Talc correctly stayed unmatched (`is_flagged: false`, not in DB yet). Confirmed working end-to-end with a real `TAVILY_API_KEY`.

---

## Score display update (2026-07-05)

Added `score_out_of_10` (e.g. `6.6`) and `star_rating` (e.g. `3.3`, out of 5) to `ScanResponse`, computed by new `derive_display_scores()` in `services/scanner.py`. `safety_score` (0-100) is unchanged — these are display-only derived fields so the existing severity-penalty math (tuned for the 100 scale) doesn't need to change. Wired into both `/scan/text` and `/scan/image`.

---

## Phase 7 — Safety Scoring Logic Finalize + Tests (Completed: 2026-07-05)

**Note on scale drift:** build_plan.md's original Phase 7 sketch assumed the SPEC.md 0-10 scale with SAFE/CAUTION/AVOID labels and a separate `scoring.py` file. Actual implementation (since Phase 3) uses the 0-100 scale with Safe/Moderate/Risky/Dangerous labels, living in `services/scanner.py` — tests were written against the real implementation, not the old sketch.

**What was built:**
- Refactored `services/scanner.py`: pulled the label-threshold logic out of `calculate_safety_score()` into a standalone `score_to_label(score: int) -> str`. Behavior is 100% identical — this just makes the boundaries independently unit-testable for any integer 0-100, not only scores reachable by summing `SEVERITY_PENALTY` values (5, 12, 22, 35 don't evenly reach every integer, e.g. 84/59/34 aren't reachable via sums, but still need boundary coverage).
- `backend/tests/test_scoring.py` (new) — covers:
  - All-safe / empty results → 100, "Safe"
  - Single HIGH → 78, "Moderate"
  - 5x CRITICAL → clamped to 0 (not negative), "Dangerous"
  - Mixed severities → exact math (100 - (5+12+22+35) = 26, "Dangerous")
  - `is_flagged=True` with `severity=None` → no deduction (guards the `if r.is_flagged and r.severity` check)
  - `is_flagged=False` with severity set anyway → no deduction (defensive, shouldn't happen in real data)
  - All 8 label-boundary values (100/85/84/60/59/35/34/0) via `score_to_label()` directly
  - `derive_display_scores()` — exact values incl. non-round ones (73 → 7.3/3.6, 85 → 8.5/4.2) and a 0-100 sweep asserting bounds never exceeded
- Added `pytest==8.3.4` to `requirements.txt`, `backend/tests/__init__.py` for package discovery.

**Type hints:** already present on all scoring functions (`split_ingredients`, `match_ingredient`, `scan_ingredients`, `calculate_safety_score`, `score_to_label`, `derive_display_scores`) — no changes needed there.

**Verified (offline):** all test assertions run manually against the real `scanner.py` logic (via lightweight stand-ins for `pydantic`/`motor`, since this sandbox has no network to install them) — all pass. **TODO next session:** run `pytest tests/test_scoring.py -v` for real from inside `backend/` with the actual venv active, to confirm no import-path surprises with real pydantic/motor installed.

**Live-tested by user (2026-07-05):** `pytest tests/test_scoring.py -v` — initially 6/22 failed with `NameError: name 'star_ratings' is not defined` (typo in `derive_display_scores` return statement — `star_ratings` vs `star_rating`). Fixed the typo. Re-ran: **all 22/22 tests pass.** Phase 7 fully done.

---

## Session Summary — 2026-07-05 (Phase 6 + Phase 7 + score display update)

Everything below was completed and verified in today's session, backend-only (frontend/Phase 8 not started yet).

**1. Phase 6 — Tavily Web Search Integration**
- New `services/search.py`: `enrich_with_research_urls()` — fetches a temporary `research_url` from Tavily for flagged chemicals missing one in MongoDB, capped at 5 calls/request, never written back to DB, degrades silently if `TAVILY_API_KEY` is unset or a call fails.
- Wired into both `POST /scan/text` and `POST /scan/image` in `routers/scan.py`, right after matching and before scoring.
- `models/schemas.py`: added `research_url: Optional[str]` to `IngredientResult`.
- `services/config.py` + `env.example`: added `TAVILY_API_KEY`.
- `requirements.txt`: added `tavily-python==0.5.0`.
- **Bug fixed:** `scanner.py::match_ingredient()` was reading a non-existent `concerns` field from MongoDB docs — actual DB field is `danger_type` (see `chemical_template.json`). Silently returned `[]` since Phase 3. Fixed to `doc.get("danger_type", [])`, and added `research_url=doc.get("research_url")` in the same place.
- **Live-verified by user:** real `/scan/text` call with Fragrance + Parabens returned real Tavily URLs (EWG Skin Deep, NCBI PMC); Talc correctly stayed unmatched.

**2. Score display update**
- Added `score_out_of_10` (e.g. `6.6`) and `star_rating` (e.g. `3.3`, out of 5) to `ScanResponse`, via new `derive_display_scores()` in `scanner.py`. `safety_score` (0-100) itself is untouched — these are pure display-derived fields for the frontend's "6.6/10" text + star widgets.

**3. Phase 7 — Safety Scoring Logic Finalize + Tests**
- Refactored `calculate_safety_score()` to pull label-threshold logic into a standalone `score_to_label(score) -> str`, so all 8 boundary values (100/85/84/60/59/35/34/0) are independently testable.
- New `backend/tests/test_scoring.py` (22 tests) covering: all-safe/empty, single/multiple severities, score clamping at 0, mixed-severity math, missing-severity edge cases, every label boundary, and `derive_display_scores()` correctness incl. non-round values.
- Added `pytest==8.3.4` to `requirements.txt`.
- **Bug found & fixed by user:** typo `star_ratings` → `star_rating` in `derive_display_scores()`'s return statement (caught by the new tests — 6/22 failed until fixed).
- **Live-verified by user:** `pytest tests/test_scoring.py -v` → **22/22 pass.**

**Files touched today:** `services/search.py` (new), `routers/scan.py`, `services/scanner.py`, `models/schemas.py`, `services/config.py`, `env.example`, `requirements.txt`, `tests/test_scoring.py` (new), `tests/__init__.py` (new), `build_plan.md` (Phase 6 + 7 marked done), `CLAUDE.md` (current focus updated).

**Status:** Phases 1-7 complete and live-verified. Phase 8 (Next.js Frontend) starting next.

---

## Phase 8 — Next.js Frontend (Completed: 2026-07-05)

**Design direction (deliberate, not templated):** clinical lab-report aesthetic — paper-white background (#FAFAF8), hairline borders, monospace (IBM Plex Mono) for scores/chemical names like a lab readout, Space Grotesk for display headings, Inter for body text. Explicitly avoided the common AI-generated defaults (cream+terracotta, dark+neon). Signature element: `ScoreGauge` — a semi-circular dial with colored hazard zones and a needle that sweeps to the reading on mount, echoing a real lab instrument rather than a generic progress bar.

**What was built** (`frontend/`, hand-authored — this sandbox has no network access to run `npx create-next-app` or `npm install`):
- `package.json`, `tsconfig.json`, `next.config.mjs`, `tailwind.config.ts` (design tokens: paper/ink/line/safe/caution/risky/danger/primary), `postcss.config.mjs`, `.env.local.example` (`NEXT_PUBLIC_API_URL`)
- `lib/types.ts` — mirrors backend `ScanResponse`/`IngredientResult` exactly (incl. `research_url`, `score_out_of_10`, `star_rating` from Phase 6/7)
- `lib/api.ts` — `scanText()` / `scanImage()`, throws parsed `detail` message from FastAPI's error responses
- `lib/tone.ts` — maps `safety_label` (Safe/Moderate/Risky/Dangerous) and `severity` (low/moderate/high/critical) to consistent color tokens, used everywhere so color logic lives in one place
- `components/ScoreGauge.tsx` — the signature element described above
- `components/Verdict.tsx` — plain-language banner (icon + one-line explanation + flagged count), colored by tone
- `components/ChemicalCard.tsx` — specimen-tag styled card: chemical name (mono), severity chip, concern pills, "Read the research" link (opens `research_url` in a new tab)
- `components/ResultCard.tsx` — top-level container: product name header, gauge, verdict, flagged-ingredient grid, **"No harmful chemicals detected" empty state** (green checkmark, pulled forward from Phase 9 since it was trivial alongside this), collapsible "All ingredients" list, "Check another product" reset button
- `components/UploadForm.tsx` — tab toggle (paste text / upload photo), optional product name, textarea with live validation, drag-and-drop image upload with **preview before submit**, client-side file type (JPEG/PNG/WebP) + size (8MB, matches backend's `MAX_IMAGE_SIZE_MB`) validation before hitting the API
- `components/Skeletons.tsx` — **`ResultSkeleton`**: shimmer skeleton shaped exactly like the real `ResultCard` (gauge circle, verdict bar, chemical card grid), so loading never causes layout jump
- `app/page.tsx` — full state machine (`idle` / `loading` / `success` / `error`), **cold-start detection**: if a request is still pending after 5s, shows a "Waking up the server…" banner above the skeleton (common on free-tier hosts with cold starts)
- `app/layout.tsx` / `app/globals.css` — Google Fonts via `next/font`, `prefers-reduced-motion` respected, visible focus rings, shimmer keyframes

**Responsive:** single-column mobile-first layout (`max-w-xl` container), chemical card grid drops to 1 column below `sm:`. Mentally verified against a 375px viewport; **not yet verified in a real browser** (no network/npm in this sandbox).

**Not yet verified live — TODO next session:**
1. `cd frontend && npm install && npm run dev` — install real deps and confirm it builds/compiles (only did bracket-balance checks here, not a real `tsc`/Next build, since `npm install` failed with a 403 in this sandbox — no network egress).
2. Copy `.env.local.example` → `.env.local`, set `NEXT_PUBLIC_API_URL=http://localhost:8000`, confirm end-to-end flow against the real running backend (text scan, image scan, error states, the >5s cold-start banner).
3. Resize browser to 375px and confirm nothing overflows/clips.
4. Confirm no API keys appear in Network tab / page source (there shouldn't be any — frontend never touches `GROQ_API_KEY`/`TAVILY_API_KEY`, only calls own backend).

---

## Phase 9 — Search-by-product-name (Completed: 2026-07-05)

**Why:** User flagged that in "Paste ingredients" mode, typing only a product name (no ingredients text) left the Scan button disabled — there was no way to scan based on product name alone. Confirmed this was a missing feature, not a bug: image mode and text mode were already independent (`canSubmit` in `UploadForm.tsx` only checked the field for the active mode).

**What was built:**
- `backend/services/product_lookup.py` (new) — `find_ingredients_by_product_name(product_name)`: Tavily search (`"<product name> ingredients list INCI"`, `max_results=4`, `search_depth="advanced"`) to gather web content, then a Groq text model (`llama-3.3-70b-versatile`) extracts ONLY the comma-separated ingredients list from that noisy content — same "extract, don't narrate" contract as `ocr.py`'s image prompt, with a `NO_INGREDIENTS_FOUND` sentinel. Raises `ValueError` with a user-facing message (suggesting manual paste/photo as fallback) when Tavily isn't configured, search returns nothing, or the LLM can't find a real ingredients list.
- `backend/routers/scan.py` — new `POST /scan/product-name` endpoint: looks up ingredients via `find_ingredients_by_product_name()`, then runs the exact same `scan_ingredients()` → `enrich_with_research_urls()` → `calculate_safety_score()` → `derive_display_scores()` pipeline as `/scan/text`. `ValueError` → 422, unexpected errors → 502.
- `backend/models/schemas.py` — new `ProductNameScanRequest` (just `product_name: str`, `min_length=2`).
- `frontend/lib/api.ts` — new `scanByProductName(productName)`.
- `frontend/components/UploadForm.tsx` — third tab "Search by name" alongside "Paste ingredients" / "Upload a photo". In this mode the single product-name field is *required* (min 2 chars) and becomes the only input shown — no ingredients textarea, no image upload. Submit button label changes to "Search & scan" in this mode.
- `frontend/app/page.tsx` — new `handleSubmitProductName()` wired the same way as the text/image handlers (same loading/error/cold-start state machine).

**Design notes:**
- Deliberately reused the existing `scan_ingredients()` pipeline rather than writing a parallel scoring path — product-name search is just a third *way of getting ingredients text*, everything downstream (matching, scoring, Tavily research-url enrichment) is identical to text/image scans.
- No new dependencies — `tavily-python` and `groq` were already in `requirements.txt` from Phases 3 and 6.
- No caching of search results — every product-name scan does a fresh Tavily + Groq call. Acceptable for v1 given Tavily's free tier and this feature's expected lower usage vs. per-ingredient research_url lookups; revisit if usage grows.

**Not yet verified live — TODO next session:**
1. Real `POST /scan/product-name` call with `TAVILY_API_KEY` + `GROQ_API_KEY` set, against a well-known product (e.g. "CeraVe Moisturizing Cream") — confirm Tavily finds sensible pages and the Groq extraction returns a plausible ingredients string, not `NO_INGREDIENTS_FOUND` or garbage.
2. Test a product name likely to have no findable ingredients list online (e.g. very obscure/local brand) — confirm the 422 message surfaces cleanly in the frontend error state, not a raw 500.
3. `cd frontend && npm run build` — confirm the new mode/props compile with real `tsc`, not just bracket-balance checks (same sandbox network limitation as Phase 8).
4. Manually click through all three tabs in a real browser to confirm the right single field is required per mode and the button never stays wrongly disabled/enabled.

---

## Phase 9 fix — snippet-only search was missing real ingredients (2026-07-05)

**Bug found by user:** Live-tested `/scan/product-name` with "Lakmē 9to5 Hya Beach Edit Lipstick + Liner Duo" → got a 422 "couldn't find ingredients" even though the user confirmed the ingredients ARE listed on the official product page (`lakmeindia.com`). User pointed out they could paste that exact URL and the ingredients were right there.

**Root cause:** `_search_sync()` called Tavily with `include_raw_content=False`, so each search result only returned a short relevance snippet, not the full page. The Lakmē product page is huge (hundreds of other products, cookie/privacy notices, etc. all on one page) — the short snippet Tavily picked for relevance didn't happen to include the "Ingredients" section, even though it exists further down the same page. Confirmed by directly fetching the URL: the ingredients (`Isododecane, Trimethylsiloxysilicate, Dimethicone, Cyclopentasiloxane, Caprylic/Capric Triglyceride`) are present in the full page HTML.

**Fix — two changes to `services/product_lookup.py`:**
1. **Direct URL support:** `find_ingredients_by_product_name()` now detects if the input is a URL (`^https?://`). If so, it skips search entirely and calls Tavily's `extract()` API on that exact URL — pulls the FULL raw page content, not a snippet. This is the reliable path when the user already knows the product page.
2. **Better search fallback:** for plain product-name input (no URL), `_search_sync()` now sets `include_raw_content=True` on the Tavily search call, so each of the top results returns full page content instead of a short snippet — much less likely to miss a deeply-buried ingredients section.
3. Raised the per-source content cap from 8,000 → 12,000 chars before handing to the Groq extraction call, since full-page content is naturally longer than snippets.
4. `UploadForm.tsx` — "Search by name" tab now explicitly invites pasting a product page link ("for the most reliable result"), not just a product name, and the field/placeholder text updated accordingly.

**Not yet verified live — TODO next session:**
1. Re-run the same Lakmē product — both as a plain name (via improved search) and as the direct URL (via new extract path) — confirm both now return the real ingredients instead of a 422.
2. Confirm `tavily-python`'s installed version actually exposes `.extract()` — if the pinned version predates that method, this will need a version bump in `requirements.txt`.
3. Test a product name with no direct URL given, to confirm the improved `include_raw_content=True` search path alone is enough for well-known international products (e.g. CeraVe) where the exact page isn't in hand.4. **Version bump (fixed pre-emptively):** `tavily-python==0.5.0` → `tavily-python>=0.5.1` in `requirements.txt`. `.extract()` isn't reliably present on 0.5.0 — some users hit `AttributeError: 'TavilyClient' object has no attribute 'extract'` on older versions per Tavily's own community forum. 0.5.1 is the earliest version whose PyPI release notes confirm `.extract()` support.

---

## Phase 9 improvement — INCIDecoder as a priority source (2026-07-05)

**User suggestion:** incidecoder.com reliably has skincare product ingredients most of the time.

**Verified:** Fetched a sample INCIDecoder product page directly — ingredients are listed cleanly and plainly (even right in the page's meta description, e.g. "...ingredients explained: Water (Aqua), Butylene Glycol, Glycolic Acid, ..."), with zero marketing noise. Much more reliable than a generic brand/retailer page for skincare specifically.

**Change to `services/product_lookup.py`:**
- New `PREFERRED_INGREDIENT_DOMAINS = ["incidecoder.com"]` constant (list, so more curated databases can be added later without touching the logic).
- New `_search_preferred_domains_sync()` — Tavily search scoped to just those domains via `include_domains`, with `include_raw_content=True`, `max_results=2`.
- `find_ingredients_by_product_name()` search order for plain product-name input (no direct URL) is now: **(1) INCIDecoder-scoped search → (2) general web search fallback** if INCIDecoder has no match. Direct-URL input (from the earlier fix) is unaffected — it always goes straight to `_extract_url_sync()`.
- Added `source_note` to the final log line so it's visible in logs which tier actually answered a given request (`curated ingredient database` vs `general web search` vs `direct URL`) — useful for judging hit-rate later.

**Design note:** Scoped to skincare/cosmetic ingredient databases only for now — INCIDecoder doesn't cover makeup shade-specific products like the Lakmē lipstick as well as it covers skincare, so the general-web fallback still matters and isn't being removed.

**Not yet verified live — TODO next session:**
1. Test a well-known skincare product (e.g. "Paula's Choice Resist Advanced Smoothing Treatment 10% AHA" or "CeraVe Moisturizing Cream") via plain name only — confirm it resolves through the INCIDecoder path (check `source=curated ingredient database` in logs) and returns accurate ingredients.
2. Test a product not on INCIDecoder (e.g. the Lakmē lipstick) — confirm it falls through cleanly to the general search path.

---

## Phase 9 fix — Tavily extract missing tab-content ingredients, httpx direct-fetch fallback added (2026-07-05)

**Bug found by user (live-tested):** Direct-URL scan of the Lakmē lipstick page (`lakmeindia.com/products/lakme-9to5-hya-beach-edit-lipstick-liner-duo`) still returned a 422 "couldn't find ingredients" even after the Phase 9 fix (direct URL support + `include_raw_content=True`). Confirmed via manual fetch that the ingredients (`Isododecane, Trimethylsiloxysilicate, Dimethicone, Cyclopentasiloxane, Caprylic/Capric Triglyceride`) genuinely are present in the page.

**Root cause (two-layered):**
1. Naive head-truncation — `_extract_url_sync()` and the final Groq prompt both did `content[:MAX_CONTENT_CHARS]` (first 12,000 chars only). This Lakmē page has huge nav/recommendation-carousel/category-tag content; if the "Ingredients" section happened to sit later in Tavily's raw_content ordering, it was silently cut before ever reaching the LLM.
2. Root cause underneath that — Tavily's `.extract()` is a static-HTML crawl. The Lakmē page renders "Ingredients / Information / Product Details" as JS-driven tabs; confirmed via new diagnostic logging that Tavily's returned content had **zero occurrences of the word "ingredient"** at all (`'ingredient' keyword present=False`) — Tavily never saw that section, no amount of smarter truncation would have helped.

**Fixes — three changes to `services/product_lookup.py`:**
1. **`_cap_content()` helper** — replaced blind `content[:MAX_CONTENT_CHARS]` head-truncation everywhere with a keyword-windowed cap: finds the first "ingredient" occurrence and keeps a window around it (6,000 chars each side), only falling back to plain head-truncation if the keyword never appears at all. Fixes truncation-order bugs on any large page, independent of the Tavily-specific issue below.
2. **Diagnostic logging** — logs raw content length + whether the "ingredient" keyword is present, right after Tavily extract, so future failures are diagnosable from logs alone instead of guessing.
3. **`_direct_fetch_sync()` fallback** — when Tavily's extracted content has no "ingredient" keyword at all, do a second, independent plain `httpx.get()` on the same URL (custom User-Agent, 10s timeout, stdlib `HTMLParser` strips `<script>/<style>` and grabs visible text) and use that instead if *it* contains the keyword. No new dependency — `httpx` was already in `requirements.txt`.

**Why this worked:** the Lakmē tab content turned out to be present in the plain server-rendered HTML (a normal GET picked it up fine) — Tavily's own crawler/extractor just handles that particular markup differently. No headless-browser/JS execution was needed here; a second static fetch was enough.

**Live-verified by user (2026-07-05):** Same Lakmē URL now goes: `Tavily extract → 12000 chars, keyword present=False` → `Direct fetch fallback succeeded (12000 chars)` → Groq extracts 99 chars → **6 ingredients, 1 flagged, score=78, 200 OK.** Full pipeline confirmed end-to-end.

**Known limitation / not yet hit:** if a page's ingredients are *only* rendered client-side via JS (not present in the server's raw HTML response at all, e.g. fully client-fetched via a separate AJAX call after page load), neither Tavily's extract nor this httpx fallback will find it — that would need a headless-browser fetch (Playwright/Selenium), which is a heavier dependency intentionally not added yet. Revisit if this shows up in practice.

---

## Phase 10 — "Good ingredients" verification (2026-07-05)

**Problem raised by user:** an ingredient was being labeled "Good" purely because it didn't match anything in our curated ~67-chemical harmful-chemicals DB. That's a "not flagged" claim, not a "verified safe" claim — our DB only covers a curated known-harmful list, so an unmatched ingredient could just as easily be something the DB never had an opinion on, not something genuinely confirmed safe. User wanted real verification behind the "Good" label — via AI's trained knowledge and/or research — before an ingredient earns that badge.

**Decision — scope of verification (user's explicit choice):**
- Trained-knowledge only, via Groq, **no Tavily/web search** for this feature. One fast batched call over the whole non-flagged list per scan, not N calls and not a slower research pass.
- Alternative considered: LLM + Tavily research per ingredient — rejected by user for latency/cost; can revisit later if accuracy issues surface.

**Decision — how to display uncertain ingredients (user's explicit choice):**
- A distinct third section, **"Uncertain / Limited Data"**, separate from both "Flagged" and "Good" — rather than folding uncertain ones into "Good" with a footnote. Keeps the positive "Good" label meaning something specific (model actually confirmed it), rather than being a dumping ground for "no data either way."

**What was built:**
- `backend/services/ingredient_verify.py` (new) — `verify_unflagged_ingredients()`: for ingredients where `is_flagged == False`, sends ONE batched Groq (`llama-3.3-70b-versatile`) call asking the model to classify each as `"verified_safe"` (only when genuinely confident, per cosmetic-science/regulatory consensus — FDA/EU CosIng/CIR-style reasoning) or `"uncertain"` (limited/mixed data, unrecognized ingredient, or any real reason for caution) — plus a short plain-language note per ingredient. Prompt explicitly instructs the model to default to `"uncertain"` whenever not confident — deliberately conservative, since overclaiming safety is worse than under-claiming it.
  - Capped at `MAX_INGREDIENTS_PER_CALL = 60` ingredients per call to keep prompt/response size bounded; any excess ingredients beyond that are simply left unverified (→ treated as uncertain downstream, never silently marked good).
  - **Does NOT touch `safety_score`** — this is purely an informational/display classification, wired in *after* scoring-relevant matching but kept fully separate from `calculate_safety_score()`. Consistent with project_rule.md: "Safety scoring NEVER done by AI."
  - Fails closed: any Groq error or JSON-parse failure leaves `verification_status = None` for all ingredients in that batch rather than crashing or guessing — and `None` is treated identically to `"uncertain"` downstream (see schema note below), so a failed verification call can never misrepresent an ingredient as safe.
- `backend/models/schemas.py` — added `verification_status: Optional[str]` (`"verified_safe" | "uncertain" | None`) and `verification_note: Optional[str]` to `IngredientResult`. Comment explicitly notes `None` must be treated as uncertain, not safe, by any consumer.
- `backend/routers/scan.py` — wired `verify_unflagged_ingredients()` into all three endpoints (`/scan/text`, `/scan/product-name`, `/scan/image`), immediately after `enrich_with_research_urls()` and before `calculate_safety_score()` (call order doesn't matter for scoring since verification never feeds into it — placed here just to mirror the existing enrichment step's pattern).
- `frontend/lib/types.ts` — added `VerificationStatus` type and the two new fields to `IngredientResult`.
- `frontend/components/ResultCard.tsx`:
  - "Good ingredients" section now filters to `verification_status === "verified_safe"` only (previously: anything simply not flagged).
  - New "Uncertain / Limited Data" section (uses the existing `caution` design token — amber, already in `tailwind.config.ts`, no new color needed) for everything non-flagged that isn't `verified_safe` — includes ingredients with `verification_status === "uncertain"` AND `null` (unverified), plus a one-line disclaimer ("informational only, not medical advice", consistent with project_rule.md forbidden #9).
  - Added `QuestionMark` icon component; the collapsible "All ingredients" list now shows three icon states (red X flagged / green check verified-safe / amber question-mark uncertain) instead of two.
  - Each ingredient chip shows its `verification_note` as a hover tooltip (`title` attribute).

**Cost/latency tradeoff (surfaced, not yet resolved):** this adds one extra Groq call to every scan. For products with large ingredient lists (40–60+), this could noticeably add to response time against the SPEC.md targets (<10s image / <5s text). Not batched/cached across scans of the same product. **Revisit if this proves too slow in practice** — options would be caching verification results by ingredient name (most cosmetic ingredients are shared across many products) or running it in parallel with `enrich_with_research_urls()` rather than sequentially.

**Live-verified (2026-07-05, user's local machine):**
1. ✅ Real `/scan/*` flow test via standalone `test_verify_live.py` (48 ingredients, real `GROQ_API_KEY`, `llama-3.3-70b-versatile`): all 14 well-established cosmetic ingredients (Water, Glycerin, Titanium Dioxide, Niacinamide, Squalane, Sodium Hyaluronate, Panthenol, Tocopherol, Xanthan Gum, Caprylic/Capric Triglyceride, Cetearyl Alcohol, Phenoxyethanol, Rosa Multiflora Fruit Extract, Disteardimonium Hectorite) correctly classified `verified_safe` with accurate plain-language notes (e.g. "Sunscreen pigment" for Titanium Dioxide, "Hyaluronic acid" for Sodium Hyaluronate). Both intentionally-fake ingredients ("Some Totally Made Up Extract 12345", "Zzyzx-Compound-9") correctly classified `uncertain` ("Unknown ingredient" / "Unrecognized chemical") — model did not hallucinate a safe verdict for unrecognized names. Result: 42 verified_safe / 6 uncertain out of 48.
2. ✅ Case-insensitive name matching confirmed via a mocked-Groq unit test (`GLYCERIN` ↔ `glycerin`, `"  water  "` ↔ `"Water"`, markdown-fence-wrapped JSON response) — all matched correctly.
3. ✅ Latency: **1.26s for 48 ingredients in one batched call** — comfortably inside the SPEC.md <5s (text) / <10s (image) targets. No caching/parallelization needed at this scale.
4. ⬜ Still pending: real-browser check of the "Uncertain / Limited Data" section rendering + tooltip (needs `npm run dev`, not runnable in this sandbox — no npm/network access here).

Also verified separately: failure-path degrades safely — a mocked Groq API exception leaves every ingredient's `verification_status = None` with no crash and nothing wrongly marked safe.

---

## Phase 11 — Polish (2026-07-05)

Audited all Phase 11 tasks against the actual codebase before doing new work — most were already done in earlier phases:
- Empty state, research-URL-new-tab, collapsible ingredient list, product-name-at-top, file type/size validation — all already present, no changes needed. (8MB image cap deliberately kept as-is — matches backend's `MAX_IMAGE_SIZE_MB`; SPEC.md's "10MB" is the stale doc, per CLAUDE.md's source-of-truth rule.)
- **Added:** `frontend/app/error.tsx` — Next.js App Router error boundary for the page tree (catches React render-time crashes, a different failure mode from the try/catch in `page.tsx`, which only catches API-call rejections). Deliberately never renders raw `error.message`/stack (project_rule.md: never expose backend/internal errors) — generic friendly message + retry button only.
- **Added:** `frontend/app/global-error.tsx` — root-layout-crash fallback (rare case; Next.js requires this file render its own `<html>/<body>` since the layout that would normally provide them is what crashed). Kept intentionally plain/inline-styled, no dependency on design tokens or fonts, since if the layout broke we can't assume anything above this component still works.

**`npm run lint` — fixed a broken ESLint setup (live-debugged with user):**
- Root cause: `frontend/package.json` had never had `eslint`/`eslint-config-next` added as devDependencies. Running `next lint` for the first time (no existing `.eslintrc`) triggers its interactive auto-installer, which tried to install `eslint@^8` AND latest `eslint-config-next@16.2.10` simultaneously — but `eslint-config-next@16.2.10` requires `eslint@>=9.0.0`, causing an `ERESOLVE` dependency conflict and total failure before lint could even run.
- Fix: manually pinned `"eslint": "^8.57.0"` and `"eslint-config-next": "14.2.18"` (exact match to the installed `next` version) in `package.json`, and added `.eslintrc.json` (`{"extends": "next/core-web-vitals"}`) so the interactive installer never triggers again.
- **Live-verified by user: `npm run lint` → zero errors.**

**`mypy . --ignore-missing-imports` — 7 real issues found across 5 files, all fixed:**
- `models/schemas.py` (×2): `Field(example=...)` — Pydantic v1 syntax, invalid under Pydantic v2 → moved to `json_schema_extra={"example": ...}`.
- `services/config.py`: `Settings()` flagged as missing the required `MONGODB_URI` argument — an expected false positive for `pydantic-settings` `BaseSettings` subclasses (the value is populated from `.env` at runtime, which mypy can't verify statically) → targeted `# type: ignore[call-arg]` with an explanatory comment, not a blanket ignore.
- `services/ocr.py`: **genuine bug, not just a type nitpick** — `response.choices[0].message.content.strip()` would crash with `AttributeError` if Groq ever returned `content: None` (e.g. a content-filtered/refused response) → fixed to `(response.choices[0].message.content or "").strip()`.
- `services/db.py` (×2): `Database.client`/`Database.db` class attributes default to `None` but were typed as non-Optional (`AsyncIOMotorClient`/`AsyncIOMotorDatabase`) → retyped as `Optional[...]`. `get_db()` now has an `assert db_instance.db is not None` guard — turns "called before `connect_db()` ran on startup" from a silent `None`-return bug into an immediate, clear `AssertionError`.
- `tests/test_scoring.py`: `severity: SeverityLevel = None` in a test helper — implicit-Optional, invalid under PEP 484 (mypy's own note pointed at this) → `Optional[SeverityLevel] = None`.
- (One non-error `note` also appeared for `product_lookup.py:152` — "annotation-unchecked" for an untyped def; informational only, not a failure, left as-is.)

**Done criteria — all met:**
- `npm run lint` → zero errors (confirmed by user)
- `mypy` clean, including one real fixed crash risk (`ocr.py`)
- All 5 async states (idle/loading/success/error + now render-crash via error boundary) handled

**Phase 11 marked complete in build_plan.md.** Not yet done: a real-browser pass to visually confirm the two new error-boundary pages look right (same sandbox limitation as everywhere else — no npm/network here).
---

## Phase 12 — Comprehensive edge-case / "always get a result" hardening (2026-07-08)

**Goal (user's explicit ask):** audit the whole app and add every edge-case check needed so that whatever the user does, they never hit a raw crash/hang — always either a real result or a clear, friendly, recoverable message.

### Backend

**`models/schemas.py`**
- `ScanRequest.ingredients_text`: added `max_length=20000` (was unbounded — a multi-MB paste was previously accepted as valid input).
- `ScanRequest.product_name` / `ProductNameScanRequest.product_name`: added `max_length=300`.

**`services/scanner.py`**
- New `MAX_INGREDIENTS_PER_SCAN = 150`. `scan_ingredients()` now raises `ValueError` if the split ingredient list exceeds this — previously an accidental essay/paragraph paste would trigger hundreds of sequential DB round-trips with no cap at all.

**`routers/scan.py`** — rewritten, centralizing the previously-duplicated (3x) matching→scoring tail into one `_finish_scan()` helper so every route gets identical, complete error handling:
- If: `ingredients_text` / `product_name` is whitespace-only (passes Pydantic's length check on raw chars but is meaningless) → explicit 400 with a clearer message than the generic "nothing parsed" one.
- If: `scan_ingredients()` raises the new `ValueError` (too many ingredients) → 400 with the exact count and cap.
- If: MongoDB itself is unreachable/times out mid-request (`PyMongoError`) → 503 "database temporarily unavailable", not a raw 500.
- If: `enrich_with_research_urls()` or `verify_unflagged_ingredients()` raise anything unexpected → caught and logged, scan continues without that enrichment rather than failing the whole request (both are informational-only by design).
- If: uploaded file has no filename → 400.
- If: file content-type isn't JPEG/PNG/WebP → 400, **and now explains HEIC specifically** (iPhones default to it) instead of just listing accepted formats.
- If: the image is huge → now rejected via **bounded chunked reading** (1MB at a time, bail the instant the cap is crossed) instead of the old `await file.read()` which fully buffered arbitrarily large uploads into memory before ever checking size.
- If: the image body is empty (0 bytes) despite a valid content-type header → 400.
- If: OCR/product-lookup raise `ValueError` (genuinely nothing found) → 422 with a suggestion to try another input method; if they raise anything else (Groq/Tavily itself failing) → 502.

**`main.py`**
- New global `Exception` handler: anything not already caught by a route logs full details server-side, but the client only ever gets a generic `"Something went wrong on our end. Please try again."` — closes the gap where an unanticipated bug would previously return FastAPI's default response with no server-side log trail.
- New `RequestValidationError` handler: FastAPI's default 422 shape for a Pydantic validation failure is `{"detail": [{"loc":.., "msg":.., "type":..}]}` — an **array of objects**, not a string. Flattened into a single readable string so the frontend's error UI (which expects a plain string) can't be handed a shape that would otherwise render as `[object Object]` or crash.
- Wired up `slowapi` (was already in `requirements.txt` but never actually used anywhere) — new `services/rate_limit.py` holds the shared `Limiter` instance (separate module to avoid a circular import between `main.py` and `routers/scan.py`). Per-IP limits: `/scan/text` 20/min, `/scan/image` 15/min, `/scan/product-name` 10/min (lowest, since it chains Tavily+Groq and is the most expensive per call). Hitting the limit returns a clean 429, not a crash or a starved server for other users.

**Timeouts on every external call** (previously none anywhere — a hung Groq or Tavily call could block a request indefinitely):
- `services/ocr.py`, `services/ingredient_verify.py`, `services/product_lookup.py`: `AsyncGroq(..., timeout=30.0)`.
- `services/product_lookup.py`: new `_call_with_timeout()` wraps every blocking Tavily/httpx call (`asyncio.wait_for`, 20s) — a timeout degrades exactly like any other failure in that file (falls through to the next fallback, or a clear `ValueError`).
- `services/search.py`: the per-chemical Tavily research-URL lookup is now wrapped the same way (15s) — a slow lookup can no longer stall the whole scan response; `research_url` just stays unset for that one chemical.

### Frontend

**`lib/api.ts`** (rewritten)
- If: the backend never responds at all → **new `AbortController`-based timeout** (30s text / 60s image & product-name) instead of relying on the browser's own multi-minute TCP timeout — the UI can no longer spin forever.
- If: the abort fires → distinguishes this from other errors with a specific "took too long, server may be waking up" message.
- If: `fetch()` throws `TypeError` (offline, DNS failure, CORS block, unreachable host — all indistinguishable at the JS level) → mapped to one friendly, actionable message instead of leaking "Failed to fetch".
- If: error response body isn't valid JSON at all (HTML error page from a proxy, empty body) → falls back to a status-code-keyed message instead of crashing on `.json()`.
- If: error `detail` is a **string** (normal case), an **array of objects** (raw Pydantic validation shape, in case it ever reaches the client unflattened), or an **array of strings** → all three now parsed correctly. *(Real bug found during this audit: the old code did `body.detail || fallback`, which for an array just returned the array itself — rendering it in JSX would have crashed with "Objects are not valid as a React child".)*
- If: the server returns 200 OK but a malformed/incomplete body (not JSON, or missing `results`/`safety_score`) → new `parseScanResponse()` validates the shape before ever handing it to `ResultCard`, throwing a clear "incomplete response" message instead of crashing deep inside rendering.
- If: `NEXT_PUBLIC_API_URL` was never configured → one-time `console.warn` (dev-facing only, not shown to the user) so a broken deploy is diagnosable immediately instead of every request just mysteriously failing.
- Status-code-specific fallback messages added for 429 / 502 / 503 / 504 / 413 / other 5xx.

**`lib/types.ts`** — `ApiErrorShape.detail` retyped to `string | Array<string | {msg, ...}>` to match reality (was typed as plain `string`, silently wrong).

**`components/UploadForm.tsx`** (rewritten)
- If: pasted text or product name is pure punctuation/whitespace (e.g. `",,, ,,"`) — passed the old `length >= 3` check trivially but has no real content → new `hasRealContent()` requires at least one letter/digit.
- If: dropped file is 0 bytes → rejected client-side with a clear message before ever hitting the network.
- If: file is HEIC/HEIF (iPhone default format, and browsers often report an empty `type` for it) → specific message explaining why + how to fix it on iPhone, instead of a generic "wrong format".
- If: file `type` is empty string but the extension is a known-good one (some mobile browsers do this for camera captures) → now accepted via extension fallback instead of being wrongly rejected.
- If: user double-clicks/double-taps submit before the parent's `disabled` prop re-renders → new local `justSubmitted` lock closes that race window immediately.
- If: pasted ingredients text or product name exceeds the backend's new `max_length` → client-side `maxLength` + `.slice()` now prevent it from ever being typed past the limit, with a live character counter once close to it (text mode).
- Object URL for the image preview is now revoked on unmount/file-change (was leaking memory on repeated pick-photo cycles) and mode-switch tabs are disabled while a submission is in flight.

**`app/page.tsx`** (rewritten)
- If: user hits "New scan" and resubmits before a slow first request has resolved → new request-generation counter ensures a late-arriving stale response can never overwrite a newer one's state.

**`components/ResultCard.tsx`**
- If: `data.results` is ever missing/not an array (defense in depth — `api.ts` already validates this, but a future caller might bypass it) → defaults to `[]` instead of crashing on `.filter()`.
- If: `total_ingredients === 0` → previously fell into the same branch as "0 flagged = all clear", which is a false-positive safety claim when there was actually nothing to check at all. Now its own distinct amber "We couldn't read any ingredients" state with a retry button.
- If: `product_name` is very long → header now truncates with an ellipsis (full name still available via title-attribute tooltip) instead of breaking the layout.

**Not yet live-verified** (same sandbox limitation as always — no npm/network here): all of the above were syntax-checked (`py_compile` for backend, manual bracket-balance parsing for frontend) but not run in a real browser/server. **TODO next session:** `npm install` (no new frontend deps added, so existing `node_modules` should still work) + `pip install -r requirements.txt` (no new backend deps either — `slowapi`/`pymongo` were already present, just newly *used*), then manually exercise: a 0-byte file drop, a HEIC photo, a >150-ingredient paste, rapid double-submit, killing the backend mid-request to see the timeout message, and a deliberately-malformed `.env` (`NEXT_PUBLIC_API_URL` pointing nowhere) to confirm the friendly network-error message appears instead of a raw "Failed to fetch".

---

## Phase 13 — Automatic fallback chains, no fabrication (2026-07-08)

**User's ask:** even in the "found nothing" cases, a professional app should still produce a result somehow.

**What's legitimate vs. not:** per `project_rule.md` ("Safety scoring NEVER done by AI" / "Never ask AI to return a verdict directly"), that principle extends to the underlying ingredient data too — this app must never fabricate/guess an ingredients list, since a wrong ingredient list produces a wrong safety score, which is actively dangerous for a product like this. So "always get a result" was implemented as **"always exhaust every legitimate, sourced path before giving up,"** not as "invent something rather than show an error."

**1. Image → product-name fallback (`services/ocr.py`, `routers/scan.py`):**
- New `extract_product_name_from_image()` — when the ingredients panel isn't visible in a photo (front-of-box shot), a second Groq vision call tries to read the product's brand/name off the *same* photo instead.
- `scan_image` now chains: OCR ingredients → (if none) OCR product name → (if found) web search for that name's real ingredients via `find_ingredients_by_product_name()` → only if *that* also fails does the user see an error.
- Still fully sourced: the fallback ingredients come from a real Tavily/web search, not a guess. New `ScanResponse.source_note` field surfaces this transparently to the user (shown as a small info banner in `ResultCard.tsx`) — e.g. *"No ingredients panel was visible in this photo — these ingredients are from a web search for 'CeraVe Moisturizing Cream', the product name read off the photo."* Never silently substitutes data without telling the user where it actually came from.
- If the user already typed a product name in the form, their explicit input wins over the photo-detected one.

**2. Product-name search — simplified-query retry (`services/product_lookup.py`):**
- New `_simplify_query()` — if the full product name (which may include a shade/variant/size, e.g. "Lakme 9to5 Lipstick - Coral Pink, 3.6g") finds nothing, retries once with just the core name (splits on `-|–—(`, caps at 6 words) before giving up. Improves hit-rate for overly-specific input without ever fabricating data.
- If this *also* finds nothing, the original clear 422 + alternatives message is unchanged — there genuinely isn't a source to draw from at that point, and inventing one would be worse than saying so.

**Not yet live-verified:** syntax-checked only (same sandbox limitation — no network/npm here). **TODO next session:** test with a real front-of-box-only photo (no ingredients panel) and confirm the OCR→name→web-search chain actually fires and returns a real result with `source_note` populated; test an overly-specific product name to confirm the simplified-query retry catches it.

---

## Phase 14 — NaraRouter reintroduced for text-only extraction (2026-07-08)

**Context:** NaraRouter was the *original* planned AI gateway (SPEC.md/CLAUDE.md/project_rule.md all reference it), but the actual Phase 3-13 implementation used Groq directly instead — CLAUDE.md documents this as an intentional divergence. Zero lines of actual code ever called NaraRouter until now.

**User's ask:** whether a product name comes from typed text or is read off a photo (the Phase 13 image→name fallback), pass that name through to NaraRouter for the ingredients-extraction step — NaraRouter doesn't support image input, so vision/OCR (`services/ocr.py`) stays on Groq directly either way.

**Design decision (user's explicit choice when asked):** if NaraRouter is configured but the call fails, **fall back to Groq automatically** rather than surfacing a hard error — availability wins over strict routing. This is a deliberate departure from project_rule.md's original "NaraRouter error → 503" line, which predates this actual implementation; noting the conflict here rather than silently ignoring the older doc.

**What was built:**
- `services/config.py` — added `NARA_ROUTER_API_KEY`, `NARA_ROUTER_BASE_URL` (defaults to `https://router.bynara.id/v1`), `NARA_TEXT_MODEL` (no default — must be set to a real model alias from NaraRouter's `/v1/models`). Leaving either the key or model blank disables NaraRouter entirely (logged once), not an error.
- `services/product_lookup.py`:
  - New `_get_nara_client()` — lazy `AsyncOpenAI` client (OpenAI-compatible SDK) pointed at `NARA_ROUTER_BASE_URL`, mirroring the existing lazy-client pattern already used for Tavily.
  - New `_extract_ingredients_text()` — the actual "pull the ingredients list out of raw web content" call now tries NaraRouter first (if configured), and falls back to the existing Groq client on ANY failure (timeout, auth, outage) or if NaraRouter isn't configured at all. Both callers of `find_ingredients_by_product_name()` — the direct `/scan/product-name` route AND the Phase 13 image→name fallback in `/scan/image` — funnel through this same function, so both automatically get NaraRouter when available, exactly as asked.
  - Since `openai` (the SDK) wasn't a dependency yet, added `openai==1.57.0` to `requirements.txt`.
- `backend.env.example` / `env.example` — documented the three new vars, explicitly noting they're optional (Groq fallback) and vision-exempt.

**Not yet live-verified:** syntax-checked only. **TODO next session:** set a real `NARA_ROUTER_API_KEY` + `NARA_TEXT_MODEL` (check `/v1/models` on the account first for the exact valid alias — decisions.md's original Jul 2026 note guessed "deepseek-3.2" but this was never confirmed against the live API), then confirm via logs that a `/scan/product-name` call actually says `"Ingredient extraction via NaraRouter (...) succeeded"` rather than silently always falling through to Groq. Also worth testing the fallback path deliberately (e.g. temporarily set an invalid `NARA_ROUTER_API_KEY`) to confirm it degrades to Groq without the user ever seeing an error.
