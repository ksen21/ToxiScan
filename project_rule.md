# project_rules.md — ToxiScan Non-Negotiable Rules

> These rules apply to EVERY session, EVERY change, EVERY file.
> When in doubt: do less, ask first, break nothing.

---

## 🔐 Security Rules (Never Break These)

| Rule | Why |
|------|-----|
| ALL secrets in `.env` file only | Exposed API keys = project dead |
| `.env` must be in `.gitignore` — verify before EVERY commit | One bad commit and keys are leaked |
| NEVER put `NARA_ROUTER_API_KEY` or `TAVILY_API_KEY` in frontend code | Keys visible in browser = exploited |
| `NEXT_PUBLIC_` prefix only for non-secret values | Next.js bundles `NEXT_PUBLIC_*` into client JS |
| Images NEVER saved to disk or any storage | Privacy requirement — process in memory, discard immediately |

**Verification step before any git commit:**
```bash
git diff --cached | grep -i "api_key\|secret\|password\|mongodb_uri"
# If this returns anything — STOP. Do not commit.
```

---

## 🧠 AI Usage Rules

| Rule | Reason |
|------|--------|
| Safety scoring NEVER done by AI | AI output varies per request — scoring must be deterministic |
| Scoring ONLY in `services/scoring.py` | Single source of truth, testable, auditable |
| Text parsing via NaraRouter text model only | Consistent with architecture decisions |
| Image extraction via NaraRouter vision model only | Groq via NaraRouter is the chosen path |
| Never ask AI to return a verdict directly | Verdict derived from score formula, not AI opinion |

---

## 🗄️ Database Rules

| Rule | Reason |
|------|--------|
| NEVER modify `chemicals` collection schema without updating SPEC.md | Schema and spec must stay in sync |
| Admin updates MongoDB directly via Atlas UI / Compass | No admin panel in v1 |
| `scan_logs` writes are async, fire-and-forget | Must never block the API response |
| MongoDB connection pooling always enabled (`maxPoolSize=10`) | Atlas M0 has 500 connection limit |
| Tavily results NOT saved back to DB automatically | Manual admin decision to add research URLs |

---

## 🌐 API Rules

| Rule | Reason |
|------|--------|
| Max 5 Tavily calls per single user request | Tavily free tier: 1,000/month |
| Tavily called ONLY when `research_url` is null in DB | Don't waste Tavily calls unnecessarily |
| When both image + text provided → image takes priority | Image is ground truth |
| CORS: allow only `localhost:3000` (dev) + Vercel domain (prod) | No wildcard CORS |
| NEVER create duplicate API routes or service functions | Keep codebase clean |

---

## 💻 Code Style Rules

### Backend (Python)

```
✅ Pydantic models for ALL request/response validation
✅ Python type hints on ALL functions
✅ Async functions for all I/O (MongoDB, NaraRouter, Tavily)
✅ try-except around all external API calls
✅ Never use raw dicts in route handlers — always use Pydantic schemas
❌ No hardcoded strings for model names — use env vars
❌ No AI model calls outside of services/
❌ No MongoDB queries outside of services/db.py
```

### Frontend (TypeScript + Next.js)

```
✅ Functional components ONLY — no class components
✅ TypeScript strict mode
✅ Tailwind ONLY for styling — no CSS modules, no styled-components
✅ Every async component must handle: loading / error / empty / success
✅ Use types from types/api.ts — never inline raw type definitions in components
❌ No new npm packages without checking if existing ones cover the need
❌ No inline styles
❌ No direct fetch calls in components — abstract to a service function
```

---

## 🧪 Testing Rules

| Rule |
|------|
| scoring.py must have unit tests before Phase 7 is marked done |
| Test all scoring edge cases: empty list, capped score, all severity levels |
| Run `npm run lint` before every commit — zero warnings allowed |
| Check no Python runtime errors on valid inputs before any commit |

---

## 🚫 Forbidden (Absolute Prohibitions)

These are the hard NOs from CLAUDE.md — revisit if anyone tries to do any of these:

1. **Do NOT store uploaded images** — to disk, S3, database, anywhere
2. **Do NOT use AI model for safety scoring** — scoring.py is pure math, always
3. **Do NOT call Tavily more than 5 times per single user request**
4. **Do NOT expose API keys in frontend code or build output**
5. **Do NOT add login/auth system in v1**
6. **Do NOT add new npm packages without checking existing ones first**
7. **Do NOT modify MongoDB `chemicals` schema without updating SPEC.md**
8. **Do NOT create duplicate routes or service functions**
9. **Do NOT give medical advice or diagnose anything** — UI copy must be clear: "informational only"
10. **Do NOT cache Tavily results back to DB** — admin decides manually

---

## 📋 Session Start Checklist

Run through this at the start of every coding session:

- [ ] Read CLAUDE.md §Current Focus — know what phase we're on
- [ ] Check `.gitignore` includes `.env` and `*.env`
- [ ] Confirm what phase of build_plan.md is in progress
- [ ] Check `decisions.md` for any pending TBD items relevant to today's work
- [ ] Update `CLAUDE.md §Current Focus` with today's session goal

---

## 📋 Before Any Git Commit Checklist

- [ ] `npm run lint` passes (zero errors)
- [ ] No Python errors (`python -c "import main"` in backend)
- [ ] `git diff --cached` — no secrets visible
- [ ] `.env` is NOT staged (`git status` — must not show `.env`)
- [ ] No `console.log` / `print` statements with sensitive data
- [ ] If schema changed → SPEC.md updated
- [ ] If architecture decision made → decisions.md updated

---

## ⚡ NaraRouter Specific Rules

- Base URL: `https://router.bynara.id/v1` — never change without updating CLAUDE.md
- Use OpenAI Python SDK with `base_url` override — not a custom HTTP client
- If model hits daily token quota → switch model alias (check `/v1/models` for alternatives)
- Always check `/v1/models` to confirm vision model name before hardcoding
- NaraRouter errors must be caught and returned as 503 (not 500) to frontend

---

## 📞 Error Handling Standards

| Error type | What to do |
|-----------|------------|
| NaraRouter API error | Catch, log, return HTTP 503 with message "AI service temporarily unavailable" |
| MongoDB connection error | Catch, log, return HTTP 503 with message "Database temporarily unavailable" |
| Tavily error | Catch, log, set research_url to null — don't surface error to user |
| Blurry/unreadable image | Return HTTP 422 with message "Could not read ingredients from image. Please try text input." |
| Empty input | Return HTTP 422 with validation error before any API call |
| Image > 10MB | Return HTTP 413 before processing |

---

## 🏷️ decisions.md Update Rule

> If you make ANY architectural, tech stack, or approach decision during a session, add it to `decisions.md` IMMEDIATELY — not at the end of the session, not next session. Now.

Format:
```
**[Month Year] Decision title**
- Reason: why this was chosen
- Alternatives considered: (if any)
```