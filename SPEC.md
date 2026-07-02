# SPEC.md — ToxiScan: Product Ingredient Safety Checker

> Version: 1.0 | Status: Pre-build | Last updated: July 2026

---

## Project Overview

**Project name:** ToxiScan

**One-line description:** A tool that lets users scan any beauty, cosmetic, hair, or body care product's ingredients (via image or text) and instantly see which chemicals are potentially cancer-causing, irritating, or harmful — with a safety rating.

**Who is this for:** Health-conscious consumers in India who want to know if their everyday beauty/personal care products contain harmful chemicals — but don't have chemistry knowledge to evaluate ingredient lists themselves.

**Core problem:** Ingredient lists on product packaging are long, complex, and unreadable for most people. Users have no way to quickly know if a product contains carcinogens or irritants. ToxiScan solves this by doing the checking automatically using AI + a curated harmful chemicals database.

---

## Core Loop

**Trigger:** User uploads a product image OR types ingredient text manually

**Action:**
- If image uploaded → Vision AI (Groq via NaraRouter) extracts product name + full ingredient list from image
- If both image + text provided → Image takes priority (image model works, not text model)
- If only text provided → Text goes directly to reasoning model (NaraRouter) for analysis
- Reasoning model cross-checks extracted ingredients against MongoDB harmful chemicals database
- Web search (Tavily) fetches latest research if research URL is missing or outdated

**Result:**
- Each detected harmful chemical shown with:
  - Chemical name (highlighted in red/orange)
  - Danger type (Carcinogen / Irritant / Sensitive Skin Issue)
  - Short 1-line description of why it's harmful
  - Research URL (if available in DB)
  - Severity badge (High / Medium / Low)
- Overall safety score out of 10
- Final verdict: SAFE / CAUTION / AVOID

**Return:** User shares result or checks another product

---

## User Stories

1. As a user, I want to take a photo of a product and see which ingredients are harmful, so I don't have to read the label myself.
2. As a user, I want to manually type or paste ingredients when the packaging photo is blurry, so I still get results.
3. As a user, I want each harmful chemical clearly listed with what it causes, so I understand the risk.
4. As a user, I want a simple 1-10 safety score and a final verdict, so I can make a quick decision.
5. As a user, I want to see the research source URL for each chemical, so I can verify the information.
6. As a user, I want the app to work instantly (under 10 seconds), so it's usable while shopping.
7. As an admin (me), I want to update the harmful chemicals list in MongoDB myself, so the database stays current without redeploying.

---

## Functional Requirements

### Input Options

- [ ] User can upload a product image (JPG/PNG/WEBP, max 10MB) from gallery or camera
- [ ] User can type/paste raw ingredient text in a textarea
- [ ] Both inputs can be provided simultaneously
- [ ] When both are provided: image model processes the image independently; if image yields different product/ingredients than typed text, image result takes priority for analysis
- [ ] If image is provided but unreadable (blurry/low light): show error "Could not read ingredients from image. Please try text input."
- [ ] If neither input provided: show validation error before any API call

### Image Processing (Vision Model)

- [ ] Image sent to Groq vision model via NaraRouter API (`https://router.bynara.id/v1`)
- [ ] Model extracts: product name, brand name, full ingredient list
- [ ] If product name visible in image: display it as "Detected Product: [name]"
- [ ] Raw extracted ingredients shown in collapsible section so user can verify
- [ ] Image processing result feeds into ingredient analysis pipeline

### Text Processing (When No Image / Text-Only)

- [ ] User-typed text sent directly to NaraRouter text reasoning model
- [ ] Model parses and normalizes ingredient names (handles INCI names, alternate spellings)
- [ ] Normalized list feeds into same analysis pipeline as image path

### Ingredient Analysis

- [ ] Backend fetches all harmful chemicals from MongoDB `chemicals` collection
- [ ] Fuzzy matching used: ingredient names matched against chemical aliases/synonyms in DB
- [ ] Each matched harmful chemical flagged with:
  - `name`: chemical name as it appears in product
  - `matched_db_name`: canonical name from DB
  - `danger_type`: array — ["Carcinogen", "Irritant", "Sensitive Skin"]
  - `description`: 1-2 sentence explanation from DB
  - `severity`: "High" | "Medium" | "Low"
  - `research_url`: string | null (from DB)
- [ ] If `research_url` is null AND web search is enabled: Tavily searches for latest research on that chemical, returns top result URL

### Web Search Integration (Tavily)

- [ ] Tavily API called ONLY when: chemical exists in DB but has no `research_url`
- [ ] Search query: `"[chemical_name] cancer carcinogen cosmetic research study"`
- [ ] Top 1 result URL stored temporarily and shown in result (NOT saved back to DB automatically)
- [ ] If Tavily finds nothing: show "No research link available" — no error shown to user
- [ ] Tavily free tier: 1,000 searches/month — rate limit on backend, max 5 Tavily calls per user request

### Safety Scoring

- [ ] Score calculated on backend, not by AI model
- [ ] Formula:
  - Start at 10
  - High severity chemical found: -2.5 per chemical (min 0)
  - Medium severity: -1.5 per chemical
  - Low severity: -0.5 per chemical
  - Cap score at 0 minimum
- [ ] Verdict based on score:
  - 8-10: ✅ SAFE
  - 5-7.9: ⚠️ CAUTION
  - 0-4.9: 🚫 AVOID

### Results Display

- [ ] Product name shown at top (from image detection or "Unknown Product" if text-only)
- [ ] Harmful chemicals section: each chemical in its own card with all details
- [ ] If zero harmful chemicals found: show "✅ No harmful chemicals detected from our database"
- [ ] Full ingredient list shown in collapsible "All Ingredients" section
- [ ] Safety score displayed as visual gauge/meter (0-10)
- [ ] Final verdict shown prominently with color (green/yellow/red)
- [ ] Each research URL opens in new tab
- [ ] "Check Another Product" button resets the form

### MongoDB Schema

**Collection: `chemicals`**
```json
{
  "_id": ObjectId,
  "name": "Formaldehyde",
  "aliases": ["formalin", "methanol", "methanal", "formic aldehyde"],
  "danger_type": ["Carcinogen", "Irritant"],
  "severity": "High",
  "description": "Known human carcinogen. Can cause skin irritation and allergic reactions.",
  "research_url": "https://www.iarc.who.int/...",
  "added_date": ISODate,
  "last_updated": ISODate
}
```

**Collection: `scan_logs`** (for future analytics, not shown to users)
```json
{
  "_id": ObjectId,
  "timestamp": ISODate,
  "input_type": "image" | "text" | "both",
  "chemicals_found": ["chemical1", "chemical2"],
  "safety_score": 7.5,
  "verdict": "CAUTION"
}
```

### Performance

- [ ] Total response time (image path): under 10 seconds on average
- [ ] Total response time (text-only path): under 5 seconds
- [ ] Frontend shows loading state with progress indicator during processing
- [ ] No full page reload — single page app behavior
- [ ] API responses streamed where possible (NaraRouter streaming enabled)

---

## Technical Constraints

**Frontend:** Next.js 14 (App Router) + TypeScript + Tailwind CSS
**Backend:** FastAPI (Python 3.11+)
**Database:** MongoDB Atlas (free tier M0 to start)
**AI Gateway:** NaraRouter (`https://router.bynara.id/v1`) — OpenAI-compatible SDK
**Vision Model:** Groq vision model via NaraRouter
**Text Reasoning Model:** NaraRouter text model (deepseek or similar)
**Web Search:** Tavily API (free tier: 1,000 searches/month)
**Frontend Hosting:** Vercel
**Backend Hosting:** Render (free tier)
**Image Upload:** Direct from browser to FastAPI (multipart/form-data) — no S3 needed, image not stored

**Environment Variables (never in code):**
- `NARA_ROUTER_API_KEY` — NaraRouter key
- `TAVILY_API_KEY` — Tavily key
- `MONGODB_URI` — MongoDB Atlas connection string
- `VISION_MODEL` — Groq model name via NaraRouter
- `TEXT_MODEL` — Text reasoning model name via NaraRouter
- `NEXT_PUBLIC_API_URL` — Backend URL (for frontend)

---

## Acceptance Criteria

- [ ] User uploads image of any beauty product → harmful chemicals listed within 10 seconds
- [ ] User types ingredients → results shown within 5 seconds
- [ ] When both image + text given with conflicting info → image analysis result shown
- [ ] Chemical with no research_url → Tavily search triggered automatically
- [ ] Safety score correctly calculated using formula (testable with known chemicals)
- [ ] Score of 9+ → shows SAFE verdict
- [ ] Score of 5-7 → shows CAUTION verdict
- [ ] Score under 5 → shows AVOID verdict
- [ ] Blurry image → shows helpful error, does not crash
- [ ] API keys NOT visible in frontend bundle (verify with browser devtools)
- [ ] App loads in under 3 seconds on mobile (test on 4G)
- [ ] MongoDB chemicals collection queryable and updatable without code change

---

## Non-Goals (What This Does NOT Do)

- This app does NOT store user-uploaded images (privacy — images processed and discarded)
- This app does NOT give medical advice or diagnose anything
- This app does NOT have user login/signup in v1
- This app does NOT have a public admin panel for chemical DB — admin updates MongoDB directly via Atlas UI or compass
- This app does NOT scan product barcodes (future feature)
- This app does NOT compare products against each other
- This app does NOT have user history/saved results in v1
- Do NOT add social sharing features in v1
- Do NOT build a mobile app — web only (but must be mobile-responsive)
- Do NOT use any AI model for scoring — scoring is pure backend calculation
- Do NOT cache Tavily results in DB automatically — manual admin decision to add research URLs

---

## Build Priority

1. **MongoDB setup** — chemicals collection schema + seed data (10-20 sample chemicals)
2. **FastAPI backend skeleton** — health check, env config, MongoDB connection
3. **Ingredient analysis endpoint** — POST /analyze/text (text-only path, no AI yet)
4. **NaraRouter text model integration** — normalize ingredient names
5. **NaraRouter vision model integration** — POST /analyze/image (image upload path)
6. **Tavily web search integration** — fallback for missing research URLs
7. **Safety scoring logic** — pure Python calculation
8. **Next.js frontend** — upload UI + results display
9. **Polish** — loading states, error states, mobile responsive
10. **Deploy** — Vercel (frontend) + Render (backend)

---

## Open Questions

- [ ] Which specific Groq vision model to use via NaraRouter? (need to check `/v1/models` list)
- [ ] Which text reasoning model on NaraRouter for ingredient parsing? (deepseek-3.2 as default?)
- [ ] Fuzzy matching threshold — how similar must ingredient name be to DB alias to count as match? (suggest: 85% similarity using rapidfuzz)
- [ ] Should scan_logs be written async (fire-and-forget) to not slow response?
- [ ] Tavily rate limit strategy — per IP or global daily counter?
