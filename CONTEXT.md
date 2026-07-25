# ResumeForge - Project Context

## Overview
AI-powered resume & cover letter builder using CrewAI agents, React frontend, and FastAPI backend. Extracts text from uploaded CVs, cleans/structures the data, generates ATS-friendly LaTeX CVs and cover letters tailored to job descriptions, and compiles them to PDF.

## Architecture
```
Frontend (React/Vite) → FastAPI Backend → CrewAI Agents → NVIDIA NIM API
                                         ↓
                                    pdflatex (MiKTeX) → PDF output
```

## Tech Stack
- **Frontend**: React 19, Vite, TailwindCSS, Lucide icons
- **Backend**: Python 3.12 (via `uv`), FastAPI, CrewAI
- **LLM**: `google/diffusiongemma-26b-a4b-it` via NVIDIA NIM API (custom requests wrapper)
- **PDF**: LaTeX → pdflatex (MiKTeX at `C:\Users\Marwan\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe`)
- **Python env**: `backend/.venv` managed by `uv` (Python 3.12.13)

## Project Structure
```
D:\Marwan\tips_hindawi_final\
├── backend/
│   ├── .env                    # NVIDIA_NIM_API_KEY, CREWAI_TRACING_ENABLED=true
│   ├── main.py                 # FastAPI server (port 8000)
│   ├── crew.py                 # CrewAI agents, tasks, pipeline
│   ├── requirements.txt        # crewai, langchain-nvidia-ai-endpoints, etc.
│   ├── tools/
│   │   ├── extractors.py       # pdfplumber + python-docx text extraction
│   │   └── nvidia_nim.py       # Custom NvidiaNimLLM (requests-based, bypasses litellm)
│   ├── templates/
│   │   ├── cv_template.tex     # ATS-friendly single-column CV template
│   │   └── cover_letter_template.tex
│   └── output/                 # Generated PDFs
├── src/
│   ├── App.jsx                 # Main app shell
│   ├── components/
│   │   ├── InputSection.jsx    # Upload, progress tracker, PDF preview
│   │   ├── HeroSection.jsx
│   │   ├── Navigation.jsx
│   │   └── FeatureSlider.jsx
│   └── index.css
└── package.json
```

## API Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/extract` | POST | Extract text from uploaded CV (PDF/DOCX) |
| `/api/clean` | POST | Clean & structure extracted text → JSON |
| `/api/generate` | POST | Generate CV/cover letter PDFs from cleaned data |
| `/api/preview/{filename}` | GET | Preview PDF in browser |
| `/api/download/{filename}` | GET | Download PDF |

## Pipeline Flow
1. **Extract** (`/api/extract`): Upload CV → pdfplumber/python-docx → raw text
2. **Clean** (`/api/clean`): Raw text → LLM (diffusiongemma) → structured JSON
3. **Generate** (`/api/generate`): Cleaned JSON + job description → LLM → LaTeX → pdflatex → PDF

## Key Design Decisions
- **Custom LLM wrapper** (`tools/nvidia_nim.py`): Uses `requests.post` directly to NVIDIA NIM API because diffusiongemma requires `chat_template_kwargs: {enable_thinking: True}` which litellm doesn't support. Inherits from `BaseLLM` for CrewAI compatibility.
- **Pipeline split**: Frontend calls extract → clean → generate separately. Generate accepts pre-cleaned JSON (no re-extraction).
- **LaTeX templates**: Single-column ATS-friendly format with custom commands (`\expentry`, `\eduentry`, `\projentry`).
- **pdflatex auto-detection**: Checks PATH first, then `AppData/Local/Programs/MiKTeX/miktex/bin/x64/pdflatex.exe`.

## Current State
- Extraction: ✅ Works
- Cleaning: ✅ Works (diffusiongemma returns valid JSON)
- CV generation: ✅ LLM generates LaTeX
- Cover letter generation: ✅ LLM generates LaTeX
- PDF compilation: Needs testing (pdflatex path confirmed, LaTeX templates use UTF-8 encoding)
- Frontend progress tracker: ✅ 4-step animated tracker with error display

## Known Issues
- Template files must be read with `encoding="utf-8"` (cp1252 fails on special chars)
- Diffusiongemma with `enable_thinking: True` can be slow (120s timeout set)
- User's CV has `experience: []` (empty) — only projects/training. CV generator must handle empty sections.

## LLM Configuration
```python
NvidiaNimLLM(
    model="nvidia-nim/diffusiongemma",
    nim_model="google/diffusiongemma-26b-a4b-it",
    api_key=NVIDIA_NIM_API_KEY,
    nim_temperature=1.0,
    nim_top_p=0.95,
    nim_enable_thinking=True,
    nim_timeout=120,
    max_tokens=4096,
)
```

## Running
```bash
# Backend
cd backend
uv run python main.py  # Runs on http://localhost:8000

# Frontend
npm run dev  # Runs on http://localhost:5173
```

## Date: 2026-07-25
