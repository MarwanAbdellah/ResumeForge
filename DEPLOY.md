# Deployment Guide

## Architecture
```
Vercel (Frontend)  →  Railway (Backend)  →  NVIDIA NIM API
     React/Vite         Python/FastAPI         diffusiongemma
                         + texlive/pdflatex
```

## Why Not Vercel for Backend?
Vercel serverless functions **cannot** run pdflatex — they have no system package manager, timeout at 60s, and are ephemeral. The backend needs a persistent server with texlive installed.

**Best combo**: Vercel (frontend) + Railway (backend)

---

## Step 1: Deploy Backend to Railway

1. Push your code to GitHub
2. Go to [railway.app](https://railway.app) → Sign in with GitHub
3. Click **"New Project"** → **"Deploy from GitHub repo"**
4. Select your repo
5. Railway will detect the `Dockerfile` in `backend/`
6. Add environment variables:
   - `NVIDIA_NIM_API_KEY` = your NVIDIA API key
   - `CREWAI_TRACING_ENABLED` = `true`
7. Click **Deploy**
8. Once deployed, copy the Railway URL (e.g., `https://your-app.up.railway.app`)
9. Test: `https://your-app.up.railway.app/api/health`

## Step 2: Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com) → Sign in with GitHub
2. Click **"Add New Project"** → Import your repo
3. Set environment variable:
   - `VITE_API_URL` = `https://your-app.up.railway.app` (your Railway URL)
4. Update `vercel.json` — replace `YOUR_BACKEND_URL.railway.app` with your actual Railway URL
5. Click **Deploy**
6. Your app is live at `https://your-app.vercel.app`

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
| `NVIDIA_NIM_API_KEY` | `nvapi-...` | Yes |
| `CREWAI_TRACING_ENABLED` | `true` | No |
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

### NVIDIA NIM API
- Free tier available with rate limits
- diffusiongemma-26b: included in free tier

---

## Local Development

```bash
# Backend
cd backend
uv run python main.py  # http://localhost:8000

# Frontend (new terminal)
npm run dev  # http://localhost:5173
```

Set `VITE_API_URL=http://localhost:8000` in `.env` for local dev.

---

## Troubleshooting

### "pdflatex not found" on Railway
The Dockerfile installs texlive. If it fails, check Railway build logs.

### CORS errors
Backend CORS allows `*.vercel.app` and `*.up.railway.app`. If you deploy elsewhere, update `main.py` CORS origins.

### Timeout errors
- pdflatex: 300s timeout (first run downloads LaTeX packages)
- NVIDIA NIM: 120s timeout (diffusiongemma with thinking enabled is slow)

### "Generation failed" on Vercel
Check Railway logs — the backend error message is passed through to the frontend.
