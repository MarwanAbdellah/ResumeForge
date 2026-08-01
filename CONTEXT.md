# ResumeForge - Project Context

## Overview
AI-powered resume & cover letter builder using a 7-agent CrewAI swarm, React frontend, and FastAPI backend. Extracts text from uploaded CVs, cleans/structures the data, generates ATS-friendly HTML CVs and cover letters tailored to job descriptions, converts them to LaTeX, and compiles A4 PDFs via pdflatex.

## Architecture
```
Frontend (React/Vite) → FastAPI Backend → CrewAI Agents → OpenRouter API (Nemotron 3 Ultra)
                                          ↓
                              HTML → LaTeX → pdflatex → PDF output
```

## Tech Stack
- **Frontend**: React 19, Vite, TailwindCSS 4, Lucide icons
- **Backend**: Python 3.12, FastAPI, CrewAI 1.15+
- **LLM**: `nvidia/nemotron-3-ultra-550b-a55b:free` via OpenRouter (litellm, `openrouter/` prefix)
- **PDF**: pdflatex (HTML → LaTeX via `html_to_latex` → compiled PDF). Requires MiKTeX/TeX Live locally; texlive is installed in the Dockerfile/CI.
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
├── templates/                      # HTML templates for CV & cover letter (LLM fill-in)
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
3. **Generate** (`/api/generate`): Cleaned JSON + job description → JD analysis → GitHub repo ranker → CV HTML → review/polish (polished HTML adopted when valid) → cover letter HTML → LaTeX → PDF

## Key Design Decisions
- **OpenRouter via litellm**: CrewAI `LLM(model="openrouter/nvidia/nemotron-3-ultra-550b-a55b:free")`. A `litellm.completion` patch strips unsupported `cache_control`/`tools` params for the free tier. Requires `OPENROUTER_API_KEY` in `backend/.env`.
- **LaTeX-only compilation**: `run_compilation` converts agent HTML → LaTeX (`html_to_latex`, BeautifulSoup) → `pdflatex`. No HTML-to-PDF fallback. `PDFLATEX_PATH` env var overrides binary lookup.
- **Deterministic section enforcer**: After LLM HTML generation (and again after review polish), `_enforce_complete_resume_sections` re-injects the verified contact header and guarantees Summary/Skills/Projects/Education sections.
- **Pipeline split**: Frontend calls extract → clean → generate separately. Generate accepts pre-cleaned JSON (no re-extraction).
- **Path traversal prevention**: Filenames validated with regex `^[\w\-]+\.pdf$` before serving.

## Security
- `.env` excluded from git (API key protection)
- Upload size limit: 10MB
- Filename validation on preview/download endpoints
- Pydantic request validation on all POST endpoints
- CrewAI telemetry/tracing disabled (`CREWAI_TELEMETRY_OPT_OUT`, `CREWAI_TRACING_ENABLED=false`)

## Date: 2026-07-25
## Last Updated: 2026-08-01 (Bug-fix pass: NameErrors, swapped API args, LaTeX-only compilation; repo split into frontend/ + backend/)
