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

## Future Decisions (TBD)

- [ ] Which specific Groq vision model alias in NaraRouter? (check /v1/models)
- [ ] Which text model alias for ingredient parsing?
- [ ] Scan logs async write strategy (motor background task vs FastAPI BackgroundTasks)
- [ ] v2: User accounts + history (likely Supabase Auth or Firebase Auth)
- [ ] v2: Barcode scanning feature
