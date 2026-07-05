# ToxiScan — Deployment Guide (Phase 12)

This sandbox has no network access and no Render/Vercel/GitHub account access,
so the actual deploy clicks have to happen on your machine. This guide walks
through exactly what to do, in order. Everything code-side (`.env.example`,
`render.yaml`, CORS config, API URL handling) is already prepared and
verified — see decisions.md Phase 12 entry.

---

## 0. Pre-flight check (already done, confirm before pushing)

- [x] `.gitignore` excludes `.env`, `venv/`, `node_modules/`, `.next/` — confirmed, no secrets tracked
- [x] `backend/services/config.py` reads all secrets from environment / `.env`, nothing hardcoded
- [x] `frontend/lib/api.ts` reads the backend URL from `NEXT_PUBLIC_API_URL`, falls back to `localhost:8000` for local dev — no hardcoded prod URL
- [x] CORS (`backend/main.py`) reads allowed origins from `settings.origins_list` (env-driven), not hardcoded
- [ ] **You should still run** `git status` and eyeball the diff before your first push, to be sure — an ounce of prevention here is cheap compared to a leaked API key.

---

## 1. Push to GitHub

```powershell
cd F:\ToxiScan
git add .
git commit -m "chore: add .env.example files, render.yaml for Phase 12 deploy prep"
git push origin main   # or whatever your branch is called
```

Then, on github.com, open the repo and confirm:
- No `.env` file is visible in `backend/` or `frontend/`
- `.env.example` (backend and frontend) ARE visible — that's correct, they contain no real secrets

---

## 2. Deploy the backend to Render

1. Go to https://dashboard.render.com -> **New -> Web Service**
2. Connect your GitHub repo, select it
3. Render should auto-detect `render.yaml` (the Blueprint file at the repo root) and pre-fill most settings. If it doesn't auto-detect, set manually:
   - **Root Directory:** `backend`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
4. Under **Environment**, add these (see `backend/.env.example` for descriptions):
   | Key | Value |
   |---|---|
   | `MONGODB_URI` | your Atlas connection string |
   | `GROQ_API_KEY` | your Groq key |
   | `TAVILY_API_KEY` | your Tavily key |
   | `APP_ENV` | `production` |
   | `ALLOWED_ORIGINS` | `http://localhost:3000` for now — **you'll update this in step 4** once you have the Vercel URL |
5. Deploy. First build takes a few minutes.
6. Once live, test the health endpoint directly:
   ```
   https://<your-service>.onrender.com/health
   ```
   Should return `{"status": "ok", "environment": "production", "db_connected": true}`. If `db_connected` is `false`, double check `MONGODB_URI` and that your Atlas cluster's IP allowlist includes `0.0.0.0/0` (Render's IPs aren't static on the free tier) — Atlas -> Network Access -> Add IP -> Allow Access from Anywhere.

**Known limitation (already documented, not a new issue):** free-tier Render spins down after 15 minutes of inactivity. First request after that takes up to ~a minute to cold-start. The frontend already handles this (`page.tsx`'s `COLD_START_DELAY_MS` + the "Waking up the server" message) — nothing new needed here.

---

## 3. Deploy the frontend to Vercel

1. Go to https://vercel.com -> **Add New -> Project**
2. Import the same GitHub repo
3. Set:
   - **Root Directory:** `frontend`
   - **Framework Preset:** Next.js (should auto-detect)
4. Under **Environment Variables**, add:
   | Key | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | your Render backend URL from step 2, e.g. `https://toxiscan-backend.onrender.com` (no trailing slash) |
5. Deploy.

---

## 4. Wire CORS back up

Now that you have the real Vercel URL:

1. Go back to Render -> your backend service -> **Environment**
2. Update `ALLOWED_ORIGINS` to include the Vercel URL:
   ```
   https://your-app.vercel.app,http://localhost:3000
   ```
3. Save — Render will redeploy automatically with the new env var.

---

## 5. Test the full flow on production URLs

Open the Vercel URL in a real browser and test all three scan modes end-to-end:
- [ ] Paste ingredients text -> get a result
- [ ] Upload a label photo -> get a result
- [ ] Search by product name -> get a result
- [ ] Confirm image scan completes in **under 10s**, text scan in **under 5s** (per SPEC.md targets) — first request after idle will be slower due to Render cold start, that's expected; test a *second* request back-to-back for the real number
- [ ] Trigger an error on purpose (e.g. submit gibberish ingredients, or a product name with no findable ingredients) and confirm the error message shown is the friendly one, never a raw stack trace or backend exception detail

---

## 6. Confirm no API keys leaked into the frontend bundle

This matters because `NEXT_PUBLIC_*` env vars ARE bundled into client-side JS by design (that's fine — it's just a URL, not a secret) — but you want to confirm nothing else slipped in.

```powershell
cd F:\ToxiScan\frontend
npm run build
```

Then check the build output doesn't contain any of your actual secret values (`GROQ_API_KEY`, `TAVILY_API_KEY`, `MONGODB_URI` value):

```powershell
Select-String -Path ".next\static\chunks\*.js" -Pattern "your-actual-groq-key-here"
```

(replace with a real substring of your actual key to search for — should return **zero matches**). Since none of these are ever read in frontend code (only `NEXT_PUBLIC_API_URL` is), this should already be clean by construction — this step is just a final confirmation.

---

## Done criteria (from build_plan.md Phase 12)

- [ ] Both URLs live and working
- [ ] Image upload -> results within 10 seconds (warm)
- [ ] Text input -> results within 5 seconds (warm)
- [ ] API keys not visible in any frontend bundle

Once all boxes are checked, come back and I'll help mark Phase 12 complete in `build_plan.md`/`decisions.md` — paste me the health-check response and a screenshot/description of a successful end-to-end test and I'll log it properly.
