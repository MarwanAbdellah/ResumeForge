# Deployment Guide

## Architecture
```
Vercel (Frontend)  →  Railway (Backend)  →  OpenRouter API
     React/Vite         Python/FastAPI      Nemotron 3 Ultra (free)
                          + pdflatex (texlive)
```

## Why Not Vercel for Backend?
Vercel serverless functions have tight timeout and memory limits that make AI-powered document generation unreliable.

**Best combo**: Vercel (frontend) + Railway (backend)

---

## Step 1: Deploy Backend to Railway

1. Push your code to GitHub
2. Go to [railway.app](https://railway.app) → Sign in with GitHub
3. Click **"New Project"** → **"Deploy from GitHub repo"**
4. Select your repo
5. Railway uses `backend/` as the Docker build root (texlive for pdflatex is installed in the image)
6. Add environment variables:
    - `LLM_MODEL` = your LiteLLM provider/model name
    - `LLM_API_KEY` = your provider API key
    - `SERPER_API_KEY` = your Serper.dev API key
    - `DOCUMENT_TOKEN_SECRET` = a long random secret
    - `ALLOWED_ORIGINS` = your Vercel frontend origin
   - `CREWAI_TRACING_ENABLED` = `false`
7. Click **Deploy**
8. Once deployed, copy the Railway URL (e.g., `https://your-app.up.railway.app`)
9. Test: `https://your-app.up.railway.app/api/health`

## Step 2: Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com) → Sign in with GitHub
2. Click **"Add New Project"** → Import your repo
3. Set the **Root Directory** to `frontend` (the `frontend/vercel.json` config is picked up automatically)
4. Set environment variable:
   - `VITE_API_URL` = `https://your-app.up.railway.app` (your Railway URL)
5. Set `VITE_API_URL` to the actual Railway URL. The Vercel rewrite is only a fallback for deployments that retain the configured backend destination.
6. Click **Deploy**
7. Your app is live at `https://your-app.vercel.app`

## Step 3: Test

1. Open your Vercel URL
2. Upload a CV PDF
3. Paste a job description
4. Click Generate — the frontend calls Railway backend for all AI/compilation work

---

## Environment Variables

### Backend (Railway)
| Variable | Value | Required |
|----------|-------|----------|
| `OPENROUTER_API_KEY` | `sk-or-...` | Yes |
| `SERPER_API_KEY` | Serper.dev key | Yes |
| `CREWAI_TRACING_ENABLED` | `false` | No |
| `PORT` | `8000` | Auto-set by Railway |

### Frontend (Vercel)
| Variable | Value | Required |
|----------|-------|----------|
| `VITE_API_URL` | `https://your-app.up.railway.app` | Yes |

---

## Free Tier Limits

### Railway
- $5 free credit/month (enough for light usage)
- ~500 hours of runtime
- 512MB RAM, 1 vCPU

### Vercel
- Hobby plan: free for personal projects
- 100GB bandwidth/month
- Serverless functions included

### OpenRouter API
- `nvidia/nemotron-3-ultra-550b-a55b:free` is free with rate limits (~20 req/min, daily cap)

---

## Local Development

```bash
# Backend
cd backend
cp .env.example .env  # add your OPENROUTER_API_KEY and SERPER_API_KEY
uv run python main.py  # http://localhost:8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev  # http://localhost:5173
```

Set `VITE_API_URL=http://localhost:8000` in a `.env` file in the `frontend/` directory for local dev.

---

## Troubleshooting

### CORS errors
Backend CORS allows `localhost:5173`, `localhost:3000`, and deployment URLs. If you deploy elsewhere, update the `ALLOWED_ORIGINS` env var on the backend.

### Timeout errors
- OpenRouter free tier: rate-limited (~20 req/min); a full generation makes several sequential LLM calls, so retries with backoff are built in. Heavy use can hit the daily free cap.

### "Generation failed" on Vercel
Check Railway logs — the backend error message is passed through to the frontend.
