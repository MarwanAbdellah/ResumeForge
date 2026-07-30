# ResumeForge - Project Context

## Overview
AI-powered resume & cover letter builder using CrewAI agents, React frontend, and FastAPI backend. Extracts text from uploaded CVs, cleans/structures the data, generates ATS-friendly HTML CVs and cover letters tailored to job descriptions, and compiles them to PDF via xhtml2pdf.

## Architecture
```
Frontend (React/Vite) → FastAPI Backend → CrewAI Agents → NVIDIA NIM API
                                          ↓
                                     xhtml2pdf → PDF output
```

## Tech Stack
- **Frontend**: React 19, Vite, TailwindCSS 4, Lucide icons
- **Backend**: Python 3.12, FastAPI, CrewAI
- **LLM**: `google/diffusiongemma-26b-a4b-it` via NVIDIA NIM API (custom requests wrapper)
- **PDF**: xhtml2pdf (HTML → PDF)
- **Testing**: Vitest (frontend), pytest (backend)

## Project Structure
```
src/
├── main.jsx
├── App.jsx
├── index.css
├── api/
│   └── client.js                 # Centralized API layer
├── components/
│   ├── Navigation.jsx
│   ├── HeroSection.jsx
│   ├── HeroContent.jsx
│   ├── VideoBackground.jsx
│   ├── LiquidGlassCard.jsx
│   ├── GridLines.jsx
│   ├── CentralGlow.jsx
│   ├── InputSection.jsx          # Main orchestrator
│   ├── FileUpload.jsx            # Drag-and-drop upload
│   ├── ManualForm.jsx            # Manual data entry
│   ├── ProgressTracker.jsx       # Step indicator
│   ├── GenerationResults.jsx     # Download/preview
│   └── Footer.jsx
└── __tests__/

backend/
├── main.py                       # FastAPI server (port 8000)
├── crew.py                       # CrewAI agents, tasks, pipeline
├── tools/
│   ├── extractors.py             # pdfplumber + python-docx extraction
│   └── nvidia_nim.py             # Custom NvidiaNimLLM wrapper
├── templates/                    # HTML templates for CV & cover letter
└── tests/
```

## API Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/extract` | POST | Extract text from uploaded CV (PDF/DOCX/TXT) |
| `/api/clean` | POST | Clean & structure extracted text → JSON |
| `/api/generate` | POST | Generate CV/cover letter PDFs from cleaned data |
| `/api/preview/{filename}` | GET | Preview PDF in browser |
| `/api/download/{filename}` | GET | Download PDF |

## Pipeline Flow
1. **Extract** (`/api/extract`): Upload CV → pdfplumber/python-docx → raw text
2. **Clean** (`/api/clean`): Raw text → LLM (diffusiongemma) → structured JSON
3. **Generate** (`/api/generate`): Cleaned JSON + job description → LLM → HTML → xhtml2pdf → PDF

## Key Design Decisions
- **Custom LLM wrapper** (`tools/nvidia_nim.py`): Uses `requests.post` directly to NVIDIA NIM API because diffusiongemma requires `chat_template_kwargs: {enable_thinking: True}` which litellm doesn't support.
- **Pipeline split**: Frontend calls extract → clean → generate separately. Generate accepts pre-cleaned JSON (no re-extraction).
- **HTML templates**: Single-column ATS-friendly format with CSS classes for PDF rendering.
- **Path traversal prevention**: Filenames validated with regex `^[\w\-]+\.pdf$` before serving.

## Security
- `.env` excluded from git (API key protection)
- Upload size limit: 10MB
- Filename validation on preview/download endpoints
- Pydantic request validation on all POST endpoints

## Date: 2026-07-25
## Last Updated: 2026-07-26 (Refactor: component split, API layer, tests, CI)
