# ResumeForge — Architecture Document

## 1. System Overview

ResumeForge is a full-stack, AI-powered resume and cover letter generation platform. It uses a multi-agent AI pipeline (CrewAI) backed by NVIDIA NIM's diffusiongemma model to extract, structure, analyze, generate, review, and compile job-tailored application documents.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                             │
│  React 19 · Vite 8 · Tailwind CSS 4 · HLS.js · Lucide Icons       │
│                                                                     │
│  ┌──────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────────┐  │
│  │  Hero    │ │ InputSection │ │  ATSChecker  │ │  Generation   │  │
│  │  Section │ │  (Orchestr.) │ │              │ │  Results      │  │
│  └──────────┘ └──────┬───────┘ └──────────────┘ └───────────────┘  │
│                      │                                              │
│              ┌───────▼────────┐                                     │
│              │  api/client.js │  ← Centralized fetch layer          │
│              └───────┬────────┘                                     │
└──────────────────────┼──────────────────────────────────────────────┘
                       │  HTTP (fetch)
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SERVER (FastAPI · Python 3.12)                    │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  main.py  (REST API · CORS · Validation · File Serving)       │ │
│  │  POST /api/extract  /api/clean  /api/generate  /api/ats-check│ │
│  │  GET  /api/preview/{id}  /api/download/{id}  /api/health     │ │
│  └──────────────┬─────────────────────────────────────────────────┘ │
│                 │                                                   │
│  ┌──────────────▼─────────────────────────────────────────────────┐ │
│  │  crew.py  (CrewAI Pipeline · 7 Agents · Helpers)              │ │
│  │                                                                │ │
│  │  Agent 1: Extraction (tool, no LLM)                           │ │
│  │  Agent 2: Structuring & Enrichment                            │ │
│  │  Agent 3: Job Description Analysis                            │ │
│  │  Agent 4: ATS Resume Generator                                │ │
│  │  Agent 5: Review & Polish                                     │ │
│  │  Agent 6: Cover Letter Writer                                 │ │
│  │  Agent 7: PDF Compilation (tool, no LLM)                      │ │
│  └──┬─────────┬──────────────────┬───────────────────────────────┘ │
│     │         │                  │                                  │
│  ┌──▼───┐ ┌──▼──────────┐ ┌────▼─────────────────────────────┐   │
│  │tools/│ │tools/        │ │templates/                        │   │
│  │extrac│ │nvidia_nim.py │ │cv_template.html                  │   │
│  │tors  │ │link_fetcher  │ │cover_letter_template.html        │   │
│  └──┬───┘ └──┬──────────┘ └──────────────────────────────────┘   │
│     │        │                                                     │
│     │        ▼                                                     │
│     │  ┌──────────────────────────────────────┐                   │
│     │  │  NVIDIA NIM API                       │                   │
│     │  │  google/diffusiongemma-26b-a4b-it     │                   │
│     │  │  (chat_template_kwargs: enable_thinking)│                   │
│     │  └──────────────────────────────────────┘                   │
│     │                                                              │
│     ▼                                                              │
│  ┌──────────────────────────────────────┐                         │
│  │  xhtml2pdf (HTML → PDF)              │                         │
│  │  output/cv_*.pdf                     │                         │
│  │  output/cover_letter_*.pdf           │                         │
│  └──────────────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Tech Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Frontend Framework** | React | 19.2.x | Component-based SPA |
| **Build Tool** | Vite | 8.1.x | Dev server, HMR, bundling |
| **CSS Framework** | Tailwind CSS | 4.3.x | Utility-first styling, glass-morphism |
| **Icons** | Lucide React | 1.26.x | Lightweight SVG icon library |
| **Video Streaming** | HLS.js | 1.6.x | Adaptive video for background |
| **Linting** | Oxlint | 1.71.x | Fast Rust-based linter (React + OXC plugins) |
| **Frontend Testing** | Vitest | 3.0.x | Unit/integration tests (jsdom) |
| **Backend Framework** | FastAPI | 0.140.x | Async REST API |
| **AI Orchestration** | CrewAI | 1.15.x | Multi-agent AI pipeline |
| **LLM** | NVIDIA NIM | — | `google/diffusiongemma-26b-a4b-it` |
| **PDF Extraction** | pdfplumber | 0.11.x | PDF text + hyperlink extraction |
| **DOCX Extraction** | python-docx | 1.1.x | Word document text extraction |
| **PDF Generation** | xhtml2pdf | 0.2.17 | HTML → PDF compilation |
| **HTTP Client** | requests | 2.31.x | NVIDIA NIM API calls |
| **Validation** | Pydantic | 2.0.x | Request/response schemas |
| **Backend Testing** | pytest + httpx | 8.0.x / 0.27.x | API and unit tests |
| **Containerization** | Docker | — | Backend deployment image |
| **Orchestration** | CrewAI | 1.15.x | Agent coordination |

---

## 3. Project Structure

```
tips_hindawi_final/
├── index.html                          # Vite entry HTML
├── package.json                        # Frontend dependencies & scripts
├── vite.config.js                      # Vite + React + Tailwind plugins
├── vitest.config.js                    # Vitest (jsdom, globals)
├── .oxlintrc.json                      # Oxlint config (react, oxc)
├── .gitignore
│
├── src/                                # ── FRONTEND SOURCE ──
│   ├── main.jsx                        # React root mount (<StrictMode>)
│   ├── App.jsx                         # Root layout: Nav → Hero → Features → Input → Footer
│   ├── index.css                       # Tailwind import, theme tokens, animations, glass effects
│   │
│   ├── api/
│   │   └── client.js                   # Centralized API layer (extract, clean, generate, URLs)
│   │
│   ├── components/
│   │   ├── Navigation.jsx              # Fixed header + mobile hamburger overlay
│   │   ├── HeroSection.jsx             # Hero container (video + grid + glow + card + content)
│   │   ├── HeroContent.jsx             # Headline, description, CTA button
│   │   ├── VideoBackground.jsx         # HLS video player with gradient overlays
│   │   ├── GridLines.jsx               # Decorative vertical grid (25/50/75%)
│   │   ├── CentralGlow.jsx             # SVG ambient glow effect
│   │   ├── LiquidGlassCard.jsx         # Glass-morphism floating card
│   │   ├── FeatureSlider.jsx           # 4-feature card grid with scroll animations
│   │   ├── InputSection.jsx            # Main orchestrator: upload/manual → generate → results
│   │   ├── FileUpload.jsx              # Drag-and-drop file upload (PDF/DOCX/TXT)
│   │   ├── ManualForm.jsx              # Manual data entry (name, email, skills, experience)
│   │   ├── Notes.jsx                   # Optional user notes textarea
│   │   ├── ProgressTracker.jsx         # 6-step progress indicator during generation
│   │   ├── GenerationResults.jsx       # Preview/download buttons + ATS report display
│   │   ├── ATSChecker.jsx              # Post-generation ATS compatibility checker
│   │   └── Footer.jsx                  # Site footer
│   │
│   └── __tests__/
│       ├── api.test.js                 # URL helper tests
│       └── ProgressTracker.test.jsx    # Component rendering tests
│
├── backend/                            # ── BACKEND SOURCE ──
│   ├── main.py                         # FastAPI app, routes, CORS, validation
│   ├── crew.py                         # CrewAI agents, tasks, pipeline orchestration
│   │
│   ├── tools/
│   │   ├── extractors.py               # PDF/DOCX/TXT text extraction (pdfplumber, python-docx)
│   │   ├── nvidia_nim.py               # Custom NvidiaNimLLM wrapper (BaseLLM subclass)
│   │   └── link_fetcher.py             # Portfolio link fetcher (GitHub/HuggingFace/Kaggle)
│   │
│   ├── templates/
│   │   ├── cv_template.html            # Single-column ATS-friendly CV template
│   │   └── cover_letter_template.html  # Formal cover letter template
│   │
│   ├── output/                         # Generated PDFs (gitignored)
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_extractors.py          # Extraction unit tests
│   │   └── test_security.py            # Path traversal prevention tests
│   │
│   ├── .env                            # NVIDIA_NIM_API_KEY (gitignored)
│   ├── .env.example                    # Template for env vars
│   ├── requirements.txt                # Python dependencies
│   ├── Dockerfile                      # Python 3.12-slim container
│   └── pytest.ini                      # pytest configuration
│
├── vercel.json                         # Vercel frontend deployment config
├── railway.json                        # Railway backend deployment config
├── DEPLOY.md                           # Deployment guide
├── CONTEXT.md                          # Project context for AI assistants
└── README.md                           # Project documentation
```

---

## 4. Frontend Architecture

### 4.1 Component Hierarchy

```
App
├── Navigation              (fixed header, mobile menu)
├── HeroSection
│   ├── VideoBackground     (HLS.js video player)
│   ├── GridLines           (decorative grid)
│   ├── CentralGlow         (SVG ambient glow)
│   ├── LiquidGlassCard     (glass-morphism card)
│   └── HeroContent         (headline, CTA)
├── FeatureSlider           (4 feature cards, scroll animation)
├── InputSection            (main orchestrator)
│   ├── FileUpload / ManualForm  (toggle between upload & manual)
│   ├── Notes               (optional user instructions)
│   ├── ProgressTracker     (6-step status during generation)
│   ├── GenerationResults   (download/preview + ATS report)
│   └── ATSChecker          (post-generation ATS analysis)
└── Footer
```

### 4.2 State Management

All state lives in `InputSection.jsx` via `useState` hooks. There is no global state library (Redux, Zustand, etc.). The component acts as the central orchestrator:

| State Variable | Type | Purpose |
|---|---|---|
| `activeMethod` | `"upload" \| "manual"` | Toggle between CV upload and manual entry |
| `uploadedFile` | `File \| null` | The selected/dropped file |
| `extractedText` | `string` | Raw text extracted by backend |
| `isExtracting` | `boolean` | Loading state for extraction |
| `manualData` | `object` | Manual form fields (name, email, skills, etc.) |
| `jobDescription` | `string` | Pasted job description text |
| `notes` | `string` | Optional AI instructions |
| `outputType` | `"cv" \| "cover_letter" \| "both"` | What to generate |
| `currentStep` | `string \| null` | Active pipeline step |
| `completedSteps` | `string[]` | Finished pipeline steps |
| `stepError` | `string \| null` | Error message if pipeline fails |
| `cvPdfPath` | `string \| null` | Generated CV PDF path |
| `clPdfPath` | `string \| null` | Generated cover letter PDF path |
| `atsReport` | `object \| null` | ATS score/strengths/suggestions |
| `cleanedData` | `object \| null` | Structured JSON from backend |
| `generationComplete` | `boolean` | Whether generation succeeded |

### 4.3 API Client (`src/api/client.js`)

A thin, centralized fetch layer with five exports:

| Function | HTTP Method | Endpoint | Purpose |
|---|---|---|---|
| `extractFile(file)` | POST | `/api/extract` | Upload CV → raw text |
| `cleanExtractedText(text)` | POST | `/api/clean` | Raw text → structured JSON |
| `generateDocuments(data, jd, type, notes, links)` | POST | `/api/generate` | Full generation pipeline |
| `getPreviewUrl(filename)` | GET | `/api/preview/{filename}` | PDF inline preview URL |
| `getDownloadUrl(filename)` | GET | `/api/download/{filename}` | PDF download URL |

The API base URL is resolved from `import.meta.env.VITE_API_URL` with a fallback to `http://localhost:8000`.

### 4.4 Styling System

- **Tailwind CSS 4** with `@tailwindcss/vite` plugin
- Custom theme tokens defined in `index.css` via `@theme` directive:
  - Colors: `accent` (#5ed29c), `dark-bg` (#070b0a), `dark-surface`, `glass-border`
  - Fonts: `inter`, `jakarta`, `instrument`
- Glass-morphism effects via custom `.glass-card-border` pseudo-element with `mask-composite`
- Apple HIG-inspired animations: `hero-fade-up`, `glass-scale-in`, press feedback (`scale(0.97)` on `:active`)
- `prefers-reduced-motion` media query for accessibility
- Easing tokens: `--ease-out`, `--ease-in-out`, `--ease-spring`

### 4.5 Video Background

Uses HLS.js to stream from Mux CDN. Falls back to native HLS on Safari. Two gradient overlays (left-to-right, bottom-to-top) ensure text readability. The video is muted, looping, and plays inline.

---

## 5. Backend Architecture

### 5.1 FastAPI Server (`main.py`)

The server runs on port 8000 (configurable via `PORT` env var) with uvicorn. It provides:

| Endpoint | Method | Request Body | Response | Purpose |
|---|---|---|---|---|
| `/api/health` | GET | — | `{status: "ok"}` | Health check |
| `/api/extract` | POST | `multipart/form-data` (file) | `{extracted_text, filename}` | Extract text from CV |
| `/api/clean` | POST | `{extracted_text: string}` | `{cleaned_data: object}` | Structure raw text → JSON |
| `/api/analyze` | POST | `{job_description: string}` | `{analysis: object}` | Analyze JD for keywords |
| `/api/ats-check` | POST | `{job_description, enriched_data}` | `{score, matched, missing, suggestions}` | CV vs JD ATS scoring |
| `/api/generate` | POST | `{cleaned_data, job_description, output_type, notes, portfolio_links}` | `{cv_pdf, cover_letter_pdf, cleaned_data, ats_report}` | Full generation pipeline |
| `/api/preview/{filename}` | GET | — | PDF (inline) | Preview PDF in browser |
| `/api/download/{filename}` | GET | — | PDF (attachment) | Download PDF file |

**CORS Configuration:**
```
localhost:5173, localhost:3000, 127.0.0.1:5173
*.vercel.app, *.up.railway.app, *.onrender.com
```

**Security Measures:**
- File upload limit: 10 MB
- Filename validation: regex `^[\w\-]+\.pdf$` (prevents path traversal)
- Pydantic models for all POST request bodies
- Async handlers use `asyncio.to_thread()` for CPU-bound CrewAI operations

### 5.2 CrewAI Pipeline (`crew.py`)

The pipeline orchestrates 7 agents in a sequential flow:

```
                        ┌─────────────────────────┐
                        │  Input: cleaned_data +   │
                        │  job_description + notes  │
                        └────────────┬────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │  Agent 3: JD Analysis            │
                    │  (analyze job description)       │
                    │  → required/preferred skills,    │
                    │    ATS keywords, strategy         │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │  Agent 2: Structuring &          │
                    │  Enrichment                      │
                    │  (normalize JSON, merge notes)   │
                    │  [skipped if already structured] │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │  Portfolio Link Fetcher          │
                    │  (tool, no LLM)                  │
                    │  → GitHub/HF/Kaggle projects     │
                    └────────────────┬────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                     │                       │
   ┌──────────▼──────────┐ ┌───────▼────────────┐ ┌───────▼────────────┐
   │  CV Pipeline         │ │  Cover Letter       │ │                     │
   │  Agent 4: Generate   │ │  Agent 6: Generate  │ │                     │
   │  Agent 5: Review     │ │                     │ │                     │
   │  Agent 7: Compile    │ │  Agent 7: Compile   │ │                     │
   │  (CV PDF)            │ │  (CL PDF)           │ │                     │
   └──────────┬──────────┘ └───────┬────────────┘ └─────────────────────┘
              │                     │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────────────────┐
              │  Output: {cv_pdf, cl_pdf,        │
              │  ats_report, cleaned_data}       │
              └─────────────────────────────────┘
```

#### Agent Definitions

| # | Agent | Role | LLM? | Tool? |
|---|---|---|---|---|
| 1 | Extraction | Extract raw text from CV files | No | pdfplumber, python-docx |
| 2 | Structuring & Enrichment | Parse raw text → normalized JSON | Yes | — |
| 3 | Job Description Analyst | Extract keywords, skills, strategy from JD | Yes | — |
| 4 | ATS Resume Generator | Generate ATS-optimized HTML CV | Yes | HTML template |
| 5 | Review & Polish | Score, fix hallucinations, polish CV | Yes | — |
| 6 | Cover Letter Writer | Generate tailored HTML cover letter | Yes | HTML template |
| 7 | PDF Compilation | Convert HTML → PDF | No | xhtml2pdf |

**All LLM agents** use the same `NvidiaNimLLM` instance configured with:
- Model: `google/diffusiongemma-26b-a4b-it`
- Temperature: 1.0, Top-p: 0.95
- Thinking enabled: `chat_template_kwargs: {enable_thinking: True}`
- Timeout: 120 seconds
- Max tokens: 4096

#### Key Helper Functions

| Function | Purpose |
|---|---|
| `_extract_json(raw)` | Parse JSON from LLM output, strip markdown fences, fix truncated JSON |
| `_extract_html(raw)` | Extract complete HTML from LLM output |
| `_normalize_phone_numbers(html)` | Post-process phone numbers to (+CC) format |
| `_run_agent_task(agent, desc, output, label)` | Run a single CrewAI task |
| `_run_agent_task_with_json(...)` | Run task + parse JSON with retry logic (up to 3 attempts) |
| `_get_crew_output(result)` | Extract raw text from CrewAI result object |

### 5.3 Custom LLM Wrapper (`tools/nvidia_nim.py`)

`NvidiaNimLLM` extends `crewai.llms.base_llm.BaseLLM` and calls the NVIDIA NIM API directly via `requests.post` instead of using litellm. This is required because diffusiongemma needs `chat_template_kwargs: {enable_thinking: True}`, which litellm doesn't support.

```
POST https://integrate.api.nvidia.com/v1/chat/completions
Authorization: Bearer {NVIDIA_NIM_API_KEY}
Body: {
  messages: [...],
  model: "google/diffusiongemma-26b-a4b-it",
  chat_template_kwargs: {enable_thinking: true},
  max_tokens: 4096,
  temperature: 1.0,
  top_p: 0.95,
  stream: false
}
```

### 5.4 Extraction Tools (`tools/extractors.py`)

| Function | Library | Input | Output |
|---|---|---|---|
| `extract_pdf(bytes)` | pdfplumber | PDF bytes | Text + discovered URLs |
| `extract_docx(bytes)` | python-docx | DOCX bytes | Paragraph text |
| `extract_text(bytes, filename)` | — | Any file | Routes to correct extractor |

PDF extraction also captures hyperlink annotations (URI and Action-based) and appends them as `--- DISCOVERED LINKS ---` for the structuring agent.

### 5.5 Portfolio Link Fetcher (`tools/link_fetcher.py`)

Fetches portfolio URLs (GitHub, HuggingFace, Kaggle, etc.) and returns structured project summaries:
- Extracts `og:title` and `og:description` meta tags
- For GitHub profiles, extracts pinned repository names via HTML parsing
- Detects platform from URL domain
- Returns: `{url, platform, title, description, repos[]}`

### 5.6 HTML Templates

**CV Template** (`cv_template.html`):
- Single-column, ATS-friendly format
- A4 page size with 0.6in margins
- Sections: Contact, Experience, Projects, Education, Skills
- CSS classes: `.contact`, `.section`, `.entry`, `.entry-header`, `.skills-line`
- Placeholders: `YOUR_NAME`, `JOB_TITLE_1`, `DATE_RANGE_1`, etc.

**Cover Letter Template** (`cover_letter_template.html`):
- Formal letter format with sender/recipient blocks
- A4 page with 1in margins
- 3-paragraph body structure (intro, fit, closing)
- Placeholders: `SENDER_NAME`, `LETTER_DATE`, `PARAGRAPH_1_INTRODUCTION`, etc.

### 5.7 PDF Compilation

Uses `xhtml2pdf` (pisa) to convert HTML → PDF:
```python
pisa.CreatePDF(html_source, dest=file_handle)
```
Output files are saved to `backend/output/` with names like `cv_{run_id}.pdf` and `cover_letter_{run_id}.pdf` where `run_id` is an 8-character UUID hex.

---

## 6. Data Flow

### 6.1 Upload Flow (CV Upload → PDF)

```
1. User drops PDF/DOCX/TXT → FileUpload component
2. Frontend: POST /api/extract (FormData with file)
3. Backend: extract_text() → pdfplumber/python-docx → raw text
4. Frontend: POST /api/clean (extracted_text)
5. Backend: run_structuring() → Agent 2 → structured JSON
6. Frontend: POST /api/generate (cleaned_data, job_description, output_type, notes)
7. Backend pipeline:
   a. Agent 3: run_jd_analysis() → JD insights JSON
   b. Agent 2: run_structuring() [skipped if already structured]
   c. Portfolio fetcher: fetch_portfolio_links()
   d. Agent 4: run_cv_generation() → HTML CV
   e. Agent 5: run_review_and_polish() → polished HTML + ATS score
   f. Agent 6: run_cover_letter_generation() → HTML cover letter
   g. Agent 7: run_compilation() → PDF files
8. Frontend receives: {cv_pdf, cover_letter_pdf, ats_report, cleaned_data}
9. GenerationResults: preview/download buttons
10. ATSChecker: POST /api/ats-check for additional ATS analysis
```

### 6.2 Manual Flow (Build from Scratch → PDF)

```
1. User fills ManualForm (name, email, skills, experience, education)
2. Frontend builds cleaned_data JSON from form fields
3. Frontend: POST /api/generate (cleaned_data, job_description, output_type, notes)
4. Backend pipeline (same as step 7 above)
```

### 6.3 ATS Check Flow

```
1. After generation, ATSChecker component appears
2. User clicks "Check" → POST /api/ats-check
3. Backend:
   a. run_jd_analysis() → extract keywords
   b. Flatten enriched_data to text
   c. Compare keywords against CV text
   d. Calculate weighted score (required=2x, preferred=1.5x, other=1x)
   e. Generate suggestions
4. Frontend renders: score ring, matched/missing keywords, suggestions
```

---

## 7. Deployment Architecture

```
┌────────────────────────────┐         ┌────────────────────────────┐
│        Vercel              │         │        Railway             │
│   (Frontend Deployment)    │         │  (Backend Deployment)      │
│                            │         │                            │
│  ┌──────────────────────┐  │  /api/* │  ┌──────────────────────┐  │
│  │  Vite Build Output   │──┼─────────┼─▶│  Docker Container     │  │
│  │  dist/               │  │  proxy  │  │  Python 3.12-slim     │  │
│  └──────────────────────┘  │         │  │  FastAPI + CrewAI     │  │
│                            │         │  │  xhtml2pdf            │  │
│  vercel.json rewrites:     │         │  └──────────┬───────────┘  │
│  /api/* → Railway URL      │         │             │              │
└────────────────────────────┘         └─────────────┼──────────────┘
                                                     │
                                                     ▼
                                          ┌─────────────────────┐
                                          │  NVIDIA NIM API     │
                                          │  diffusiongemma-26b │
                                          └─────────────────────┘
```

**Vercel (Frontend):**
- Static site hosting from `dist/`
- Rewrites `/api/*` to Railway backend URL
- Free tier: 100GB bandwidth/month

**Railway (Backend):**
- Docker-based deployment from `backend/Dockerfile`
- Health check: `GET /api/health`
- Auto-restart on failure (max 3 retries)
- Environment variables: `NVIDIA_NIM_API_KEY`, `CREWAI_TRACING_ENABLED`
- Free tier: $5 credit/month, 512MB RAM, 1 vCPU

**Local Development:**
- Frontend: `npm run dev` → `http://localhost:5173`
- Backend: `uv run python main.py` → `http://localhost:8000`
- Set `VITE_API_URL=http://localhost:8000` for local API connection

---

## 8. Security Architecture

### 8.1 Path Traversal Prevention

```python
SAFE_FILENAME = re.compile(r"^[\w\-]+\.pdf$")
```

All `/api/preview/{filename}` and `/api/download/{filename}` requests validate filenames against this regex. Only alphanumeric characters, hyphens, and underscores are allowed, and the file must end with `.pdf`.

### 8.2 Upload Security

- Maximum file size: 10 MB (`MAX_UPLOAD_BYTES`)
- File type validation on frontend (PDF, DOCX, TXT)
- Backend extraction dispatches by file extension

### 8.3 Environment Security

- `.env` files excluded from git via `.gitignore`
- API keys never exposed to frontend
- CORS restricted to known origins

### 8.4 Request Validation

All POST endpoints use Pydantic models:
- `CleanRequest`: requires `extracted_text: str`
- `GenerateRequest`: requires `cleaned_data: dict`, `job_description: str`
- `AnalyzeRequest`: requires `job_description: str` (min 20 chars)
- `ATSCheckRequest`: requires `job_description: str`, `enriched_data: dict`

### 8.5 Zero Fabrication Rules

All agent prompts explicitly enforce:
- Parse ONLY what is explicitly written in the input
- Do NOT add skills, tools, or certifications not mentioned
- Do NOT invent bullet points, achievements, or metrics
- If a field is empty, leave it out entirely
- The review agent (Agent 5) performs hallucination detection

---

## 9. Testing Strategy

### 9.1 Frontend Tests (Vitest)

| Test File | Framework | What It Tests |
|---|---|---|
| `api.test.js` | Vitest | `getPreviewUrl()` and `getDownloadUrl()` URL construction |
| `ProgressTracker.test.jsx` | Vitest + Testing Library | Renders all 6 steps, error display, completed step marking |

**Config:** jsdom environment, globals enabled, JSX automatic transform.

### 9.2 Backend Tests (pytest)

| Test File | What It Tests |
|---|---|
| `test_extractors.py` | TXT extraction, PDF extraction, DOCX extraction, empty paragraphs, unsupported file types |
| `test_security.py` | `SAFE_FILENAME` regex: valid filenames, path traversal rejection, special char rejection, non-PDF rejection |

**Config:** `pytest.ini` sets `testpaths = tests`, auto-discovers `test_*.py` files.

### 9.3 Running Tests

```bash
# Frontend
npm test          # vitest run
npm run test:watch  # vitest (watch mode)

# Backend
cd backend
pytest tests/ -v
```

---

## 10. Key Design Decisions

### 10.1 Custom LLM Wrapper

**Decision:** Build a custom `NvidiaNimLLM` class extending CrewAI's `BaseLLM` instead of using litellm.

**Reason:** NVIDIA NIM's diffusiongemma model requires `chat_template_kwargs: {enable_thinking: True}` in the API payload. litellm doesn't support passing this parameter. The custom wrapper uses `requests.post` directly to the NIM API endpoint.

### 10.2 Pipeline Split

**Decision:** Frontend calls extract → clean → generate as separate API calls, rather than a single monolithic endpoint.

**Reason:**
- Allows frontend to show intermediate results (extracted text preview)
- Enables "Build from Scratch" mode (skips extraction)
- Provides granular error handling per step
- Allows the user to review extracted text before generation

### 10.3 HTML Templates for PDF

**Decision:** Generate HTML first, then convert to PDF via xhtml2pdf, rather than generating PDF directly.

**Reason:**
- LLMs are much better at generating HTML than raw PDF
- HTML templates are easy to customize and maintain
- xhtml2pdf handles CSS-based layout reliably
- Single-column format ensures ATS compatibility

### 10.4 Graceful Review Failure

**Decision:** Agent 5 (Review & Polish) failures are non-fatal — the pipeline continues with the unreviewed HTML.

**Reason:** The review step is quality improvement, not a hard requirement. If the review agent fails or returns malformed JSON, the previously generated CV is still usable. This prevents the entire pipeline from failing for a cosmetic step.

### 10.5 State in InputSection

**Decision:** All application state lives in `InputSection.jsx` via useState hooks, with no global state management.

**Reason:** The application has a linear flow with a single orchestration point. InputSection is the only component that needs all the state. Passing state down to child components is manageable given the component tree depth (max 2 levels). Adding Redux/Zustand would be unnecessary complexity.

### 10.6 Already-Structured Data Detection

**Decision:** Skip the structuring agent if the input data already contains `name`, `experience`, `education`, and `skills` keys.

**Reason:** When users select "Build from Scratch" and fill the manual form, the frontend constructs a pre-structured JSON. Running it through the structuring agent again would be redundant and could lose information.

---

## 11. Agent System Prompt Design

Each agent's `backstory` and task `description` follow a consistent pattern:

1. **Role Definition** — Clear statement of what the agent does
2. **Zero Fabrication Rule** — Explicit instruction not to invent content
3. **Input Specification** — Exact JSON schema or data format expected
4. **Output Specification** — Exact JSON schema or HTML format expected
5. **Edge Case Handling** — What to do with empty/missing fields
6. **Post-Processing** — Phone normalization, URL handling, date formatting

The structuring agent is the most constrained: it must parse raw text without adding any information not present in the source. The generation agents have more creative freedom but are still bound by the zero fabrication rule.

---

## 12. Error Handling

### 12.1 Frontend

- Extraction errors: displayed in the file upload preview area
- Generation errors: displayed below the progress tracker via `stepError`
- ATS check errors: displayed inline in the ATSChecker component
- All errors use a red-tinted panel with an alert icon

### 12.2 Backend

- HTTP exceptions: raised with specific status codes (400, 413, 404, 500)
- CrewAI failures: caught and re-raised as `RuntimeError` with descriptive messages
- JSON parse failures: retry up to 3 times with logging
- Review failures: logged as warnings, pipeline continues without review
- All 500 errors include `traceback.print_exc()` for server-side debugging

### 12.3 PDF Compilation

- xhtml2pdf errors: checked via `status.err`
- Empty PDF detection: verified via `path.stat().st_size == 0`
- Both conditions raise `RuntimeError` with specific messages

---

## 13. Performance Considerations

| Concern | Mitigation |
|---|---|
| LLM latency (diffusiongemma is slow) | 120s timeout, thinking enabled for quality over speed |
| Blocking CrewAI in async FastAPI | `asyncio.to_thread()` wraps all synchronous pipeline calls |
| Large file uploads | 10 MB limit enforced before extraction |
| Video background | HLS adaptive streaming, muted autoplay with fallback |
| CSS animations | `prefers-reduced-motion` support, GPU-accelerated transforms |
| PDF generation | Synchronous xhtml2pdf in thread pool, output cached on disk |
| Portfolio fetching | 8s timeout per URL, graceful degradation on failure |

---

## 14. Environment Variables

| Variable | Location | Required | Purpose |
|---|---|---|---|
| `NVIDIA_NIM_API_KEY` | `backend/.env` | Yes | NVIDIA NIM API authentication |
| `CREWAI_TRACING_ENABLED` | `backend/.env` | No | Enable CrewAI tracing logs |
| `PORT` | Railway env | No | Backend port (default: 8000) |
| `VITE_API_URL` | Frontend `.env` | No | Backend URL (default: localhost:8000) |

---

## 15. Dependency Map

```
Frontend Dependencies:
  react → react-dom
  tailwindcss → @tailwindcss/vite → vite
  hls.js (video streaming)
  lucide-react (icons)

Backend Dependencies:
  fastapi → uvicorn, python-multipart, pydantic
  crewai → langchain-nvidia-ai-endpoints
  pdfplumber (PDF extraction)
  python-docx (DOCX extraction)
  xhtml2pdf (HTML → PDF)
  requests (NVIDIA NIM API)
  python-dotenv (env loading)
  pytest, httpx (testing)
```

---

## 16. Future Considerations

| Area | Potential Improvement |
|---|---|
| State Management | Migrate to Zustand or React Context for shared state |
| Streaming | Implement SSE/WebSocket for real-time pipeline progress |
| Caching | Cache JD analysis results for repeated job descriptions |
| Rate Limiting | Add per-user rate limits on generation endpoints |
| Auth | Add user accounts to save/retrieve past generations |
| Templates | Allow users to choose from multiple CV templates |
| DOCX Export | Add python-docx generation for Word output |
| Multi-language | Support non-English resumes and job descriptions |
| Unit Tests | Expand frontend component test coverage |
| E2E Tests | Add Playwright/Cypress integration tests |
