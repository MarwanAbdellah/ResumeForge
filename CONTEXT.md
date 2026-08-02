# ResumeForge - Project Context

## Overview
AI-powered resume & cover letter builder using a structured CrewAI workflow, React frontend, and FastAPI backend. Extracts text from uploaded CVs, validates candidate JSON, tailors content to job descriptions, renders deterministic Jinja2 LaTeX templates, and compiles A4 PDFs via pdflatex.

## Architecture
```
Frontend (React/Vite) → FastAPI Backend → CrewAI Agents → OpenRouter API (Nemotron 3 Ultra)
                                          ↓
                              Pydantic JSON → Jinja2 LaTeX → pdflatex → PDF output
```

## Tech Stack
- **Frontend**: React 19, Vite, TailwindCSS 4, Lucide icons
- **Backend**: Python 3.12, FastAPI, CrewAI 1.15+
- **LLM**: `nvidia/nemotron-3-ultra-550b-a55b:free` via OpenRouter (litellm, `openrouter/` prefix)
- **PDF**: pdflatex (validated Pydantic data → Jinja2 LaTeX → compiled PDF). Requires MiKTeX/TeX Live locally; texlive is installed in the Dockerfile/CI.
- **Testing**: Vitest (frontend), pytest (backend)

## Project Structure
```
frontend/
├── index.html
├── package.json
├── vite.config.js / vitest.config.js / .oxlintrc.json
├── vercel.json                     # Frontend deploy config (Vercel root = frontend/)
├── public/
└── src/
    ├── main.jsx
    ├── App.jsx
    ├── index.css
    ├── api/
    │   └── client.js               # Centralized API layer
    ├── components/
    │   ├── Navigation.jsx
    │   ├── HeroSection.jsx / HeroContent.jsx / VideoBackground.jsx
    │   ├── LiquidGlassCard.jsx / GridLines.jsx / CentralGlow.jsx
    │   ├── FeatureSection.jsx      # Tabs between ResumeCreator & ATSCheckerTool
    │   ├── FeatureSlider.jsx
    │   ├── ResumeCreator.jsx       # Main generation flow + pre-gen gap interview
    │   ├── ATSCheckerTool.jsx      # Standalone ATS audit + gap recalibration
    │   ├── FileUpload.jsx          # Drag-and-drop upload
    │   ├── ManualForm.jsx          # Manual data entry
    │   ├── ProgressTracker.jsx     # Step indicator / observability drawer
    │   ├── GenerationResults.jsx   # Download/preview
    │   ├── Notes.jsx
    │   └── Footer.jsx
    └── __tests__/

backend/
├── main.py                         # FastAPI server (port 8000)
├── crew.py                         # 7 CrewAI agents, tasks, pipeline, LaTeX compilation
├── tools/
│   ├── extractors.py               # pdfplumber + python-docx extraction + URL extraction
│   └── link_fetcher.py             # GitHub/portfolio fetcher + SerperDev web search
├── templates/                      # Jinja2 LaTeX templates
└── tests/
```

## API Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/extract` | POST | Extract text from uploaded CV (PDF/DOCX/TXT) |
| `/api/clean` | POST | Clean & structure extracted text → JSON |
| `/api/analyze` | POST | Analyze a job description (JD agent) |
| `/api/ats-check` | POST | Agentic ATS audit of structured data vs JD |
| `/api/ats-gap-inquire` | POST | Merge candidate gap answers + re-run ATS audit |
| `/api/generate` | POST | Generate CV/cover letter PDFs from cleaned data |
| `/api/preview/{filename}` | GET | Preview PDF in browser |
| `/api/download/{filename}` | GET | Download PDF |

## Pipeline Flow
1. **Extract** (`/api/extract`): Upload CV → pdfplumber/python-docx → raw text + URLs
2. **Clean** (`/api/clean`): Raw text → LLM → structured JSON (optionally enriched with live GitHub data)
3. **Generate** (`/api/generate`): Validated candidate JSON + job description → structured optimization → ATS review → Jinja2 LaTeX → PDF

## Key Design Decisions
- **OpenRouter via litellm**: CrewAI `LLM(model="openrouter/nvidia/nemotron-3-ultra-550b-a55b:free")`. A `litellm.completion` patch strips unsupported `cache_control`/`tools` params for the free tier. Requires `OPENROUTER_API_KEY` in `backend/.env`.
- **Deterministic rendering**: CrewAI returns validated Pydantic models; `renderers/latex.py` injects them into Jinja2 templates before `pdflatex`. No LLM-generated markup is accepted.
- **Pipeline split**: Frontend calls extract → clean → generate separately. Generate accepts pre-cleaned JSON (no re-extraction).
- **Path traversal prevention**: Filenames validated with regex `^[\w\-]+\.pdf$` before serving.

## Security
- `.env` excluded from git (API key protection)
- Upload size limit: 10MB
- Filename validation on preview/download endpoints
- Pydantic request validation on all POST endpoints
- CrewAI telemetry/tracing disabled (`CREWAI_TELEMETRY_OPT_OUT`, `CREWAI_TRACING_ENABLED=false`)

## Date: 2026-07-25
## Last Updated: 2026-08-02 (Observability: backend/observability/* correlation context + JSON event log + Prometheus /metrics + request-id middleware; frontend client sends X-Session-ID)

## Observability
- `backend/observability/context.py`: `ContextVar`-based request/session/generation/stage correlation, propagated across `asyncio.to_thread`.
- `backend/observability/events.py`: sanitized JSON pipeline events (`emit_event`, per-generation ring buffer `get_events`, `stage_span` context manager).
- `backend/observability/metrics.py`: dependency-free Prometheus-style counters/timings registry.
- `backend/observability/logging.py`: structured JSON `logging.Formatter` (timestamp/level/logger/message + correlation ids).
- `backend/main.py`: `observability` HTTP middleware assigns request/session ids, emits request events, attaches `X-Request-ID`/`X-Session-ID`/`X-Generation-ID` headers; `/metrics` Prometheus endpoint; `/api/generate` binds `generation_id`.
- `backend/services/ai_service.py` & `generation_service.py`: `stage_span` around CrewAI tasks and render/compile phases with token-usage events and AI/generation metrics.
- `frontend/src/api/client.js`: persists a session id across the app and sends it as `X-Session-ID` for end-to-end correlation.
