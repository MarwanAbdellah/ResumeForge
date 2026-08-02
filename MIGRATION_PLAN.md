# ResumeForge Production Architecture Migration

## Target Structure

```text
backend/
  api/
    routers/
      health.py
      extraction.py
      analysis.py
      generation.py
      documents.py
  config/
    agents.yaml
    tasks.yaml
    settings.py
  crew/
    __init__.py
    agents.py
    tasks.py
    crew.py
  models/
    schemas.py
  services/
    extraction_service.py
    analysis_service.py
    generation_service.py
    portfolio_service.py
    document_service.py
  renderers/
    latex.py
  validators/
    urls.py
    uploads.py
  utils/
    logging.py
    request_id.py
  templates/
    resume.tex.j2
    cover_letter.tex.j2
  tests/
```

The migration now uses the official `@CrewBase` structure, YAML-configured agents and tasks, typed Pydantic outputs, service-layer orchestration, deterministic Jinja2 rendering, signed document access, SSRF validation, upload limits, and bounded compilation.

## Responsibilities

`api/routers` owns HTTP concerns only: request parsing, authentication, status codes, and response serialization.

`services` owns application workflows and has no HTML or HTTP response logic.

`crew` owns CrewAI object construction and agent orchestration.

`config` owns environment settings and declarative agent/task definitions.

`models` owns validated domain and transport models.

`validators` owns upload, URL, and business-rule validation.

`renderers` owns deterministic conversion from validated models to LaTeX.

`templates` owns layout and typography only. Templates never contain candidate-specific data.

`tests` is divided into unit, integration, rendering, security, and end-to-end suites.

## CrewAI Agents

The extraction agent reads source text and returns source-supported facts.

The structuring agent normalizes those facts into `Candidate` JSON.

The job analysis agent extracts requirements and ATS priorities into `JobDescription` JSON.

The optimization agent tailors wording and ordering without adding unsupported facts.

The cover-letter agent returns `CoverLetter` JSON containing recipient data, salutation, paragraphs, and signoff.

The ATS review agent returns bounded `ATSReport` JSON.

The portfolio agent summarizes only verified external evidence.

Each agent is configured in `config/agents.yaml`. Each task is configured in `config/tasks.yaml`; Python only supplies inputs and instantiates CrewAI objects.

## Pydantic Models

`Candidate` contains identity, summary, experience, education, projects, certifications, skills, and links.

`Experience`, `Education`, and `Project` are independently validated nested models.

`JobDescription` contains source text, title, requirements, and keywords.

`CoverLetter` contains structured letter content rather than markup.

`ATSReport` bounds score values to 0-100 and validates list fields.

Transport request/response models should extend these domain models instead of accepting unrestricted dictionaries.

## Rendering Pipeline

```text
Uploaded document
  -> extraction service
  -> Candidate JSON
  -> Pydantic validation
  -> CrewAI structured optimization
  -> Pydantic validation and repair
  -> Jinja2 resume.tex.j2 / cover_letter.tex.j2
  -> isolated LaTeX compiler
  -> private PDF storage
  -> signed, expiring document URL
```

The target pipeline contains no LLM-generated HTML, CSS, or LaTeX. Layout is entirely deterministic and controlled by templates.

## API Endpoints

`GET /api/health` reports application and compiler readiness.

`POST /api/extract` accepts bounded PDF, DOCX, or TXT uploads and returns extracted text plus validated public links.

`POST /api/clean` converts extracted text into validated `Candidate` data.

`POST /api/analyze` returns validated job requirements and ATS priorities.

`POST /api/ats-check` returns a bounded ATS report.

`POST /api/ats-gap-inquire` validates additional candidate evidence and reruns the ATS workflow.

`POST /api/generate` accepts validated candidate and job data, creates PDFs, and returns signed document access.

`GET /api/preview/{filename}` and `GET /api/download/{filename}` require a generation-scoped signed token.

## Request Lifecycle

1. React validates the selected file and creates an abortable request.
2. FastAPI applies rate limits, CORS policy, upload limits, and file validation.
3. The extraction service parses the document without fetching arbitrary URLs.
4. Candidate text is sent to the structuring task and validated with Pydantic.
5. Job analysis is cached by normalized job-description hash.
6. Portfolio URLs pass HTTPS, hostname, DNS, private-network, redirect, and response-size checks.
7. Generation tasks return structured JSON only.
8. The renderer produces LaTeX from validated models.
9. A bounded compiler worker produces PDFs in isolated temporary storage.
10. The document service returns filenames plus an expiring signed token.
11. React builds tokenized preview/download URLs and announces progress and errors accessibly.

## Migration Phases

### Phase 1: Safety Boundary

Completed in the current migration: remove candidate-specific production fallbacks, add signed document access, restrict uploads, validate outbound URLs, add compiler timeout, restrict CORS, add rate limiting, and remove raw error responses.

Risk: existing clients that directly call PDF URLs without a token must update to use the generation response token.

### Phase 2: Domain Models

Replace unrestricted request dictionaries with transport models built from `models.schemas`. Add repair-and-retry handling for invalid CrewAI JSON. Reject invalid output before rendering.

Risk: malformed historical payloads may be rejected instead of producing partial output. Return actionable validation errors.

### Phase 3: Structured CrewAI

Use `crew/crew.py`, `crew/agents.py`, and `crew/tasks.py` with YAML-backed configuration, typed task outputs, and explicit task contexts. Remove prompts that request HTML and require JSON schemas.

Risk: prompt output shape changes. Add fixture-based prompt tests and keep a compatibility adapter during rollout.

### Phase 4: Deterministic Rendering

Use `renderers/latex.py` and the Jinja2 templates as the only rendering path. Keep layout snapshots and extract text from compiled PDFs for regression testing.

Risk: visual differences in generated PDFs. Compare representative fixture PDFs before deleting the legacy renderer.

### Phase 5: Service and Router Split

Move endpoint logic from `main.py` into routers and services. Keep route paths and response keys stable. Add request IDs and structured logging at the application boundary.

Risk: dependency wiring errors. Run endpoint integration tests against the assembled application.

### Phase 6: Async Jobs and Storage

Move generation and compilation to a durable background queue. Store PDFs in private object storage and issue signed URLs. Add cleanup, retries, cancellation, and job status endpoints.

Risk: job state consistency. Use idempotency keys and persistent job records.

### Phase 7: Production Operations

Add metrics, token/latency logging, tracing, error reporting, dependency lockfiles, CI coverage thresholds, Docker scanning, and deployment smoke tests.

## Testing Strategy

Unit tests cover schemas, URL validation, token signing, HTML/LaTeX escaping, and renderer output.

Integration tests cover every API route, invalid payloads, rate limits, CORS, document authorization, and compiler failures.

Rendering tests compile representative resumes and cover letters and assert extracted PDF text.

Prompt tests use fixed fixtures to verify valid JSON, no fabrication, bounded fields, and repair behavior.

End-to-end tests cover upload through tokenized PDF download in a browser-like environment.

## Remaining Risks

The current in-memory rate limiter is process-local. It must move to Redis or an edge gateway for multi-instance deployment.

The current signed-token secret falls back to an ephemeral process secret for local development. Production must set `DOCUMENT_TOKEN_SECRET`.

PDF storage is still local filesystem storage. Production should use private object storage before horizontal scaling.

Full user authentication and account ownership remain separate from anonymous generation-scoped document access.
