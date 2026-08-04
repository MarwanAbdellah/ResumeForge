import os
import re
import json
import asyncio
import logging
import time
from uuid import uuid4
from collections import defaultdict, deque
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
from observability.logging import configure_logging
configure_logging()
logger = logging.getLogger(__name__)

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from models.api import ATSCheckRequest, AnalyzeRequest, CleanRequest, GapInquireRequest, GenerateRequest
from models.pipeline import CandidateEvidenceModel
from models.schemas import ATSReport, Candidate
from security import create_document_token, validate_document_token
from services.document_service import DocumentService
from services.generation_service import GenerationService
from services.ats_postprocess import postprocess_ats_report
from services.pipeline_service import PipelineService
from observability.context import bind_context, new_context, reset_context, current_context
from observability.events import emit_event, get_events
from observability.metrics import metrics

app = FastAPI(title="ResumeForge API", version="1.0.0")
_pipeline_service: PipelineService | None = None
_generation_service: GenerationService | None = None


def get_pipeline_service() -> PipelineService:
    global _pipeline_service
    if _pipeline_service is None:
        _pipeline_service = PipelineService()
    return _pipeline_service


def get_generation_service() -> GenerationService:
    global _generation_service
    if _generation_service is None:
        _generation_service = GenerationService(get_pipeline_service().ai, DocumentService())
    return _generation_service
_rate_limit_window = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
_rate_limit_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "20"))
_request_history: dict[str, deque[float]] = defaultdict(deque)

SAFE_FILENAME = re.compile(r"^[\w\-]+\.pdf$")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174",
    ).split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "X-Session-ID", "X-Request-ID"],
)


@app.middleware("http")
async def observability(request: Request, call_next):
    context = new_context(request.headers.get("X-Request-ID"), request.headers.get("X-Session-ID"))
    token = bind_context(context)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000)
        metrics.increment("resumeforge_requests_total", route=request.url.path, method=request.method, status=response.status_code)
        emit_event("request", "completed", duration_ms=duration_ms, status_code=response.status_code)
        response.headers["X-Request-ID"] = context.request_id
        response.headers["X-Session-ID"] = context.session_id
        if context.generation_id:
            response.headers["X-Generation-ID"] = context.generation_id
        return response
    except Exception:
        duration_ms = round((time.perf_counter() - started) * 1000)
        metrics.increment("resumeforge_requests_total", route=request.url.path, method=request.method, status="error")
        emit_event("request", "failed", duration_ms=duration_ms)
        raise
    finally:
        reset_context(token)


@app.middleware("http")
async def rate_limit(request, call_next):
    if request.url.path == "/api/health":
        return await call_next(request)
    client = request.client.host if request.client else "unknown"
    key = f"{client}:{request.url.path}"
    now = time.monotonic()
    history = _request_history[key]
    while history and now - history[0] >= _rate_limit_window:
        history.popleft()
    if len(history) >= _rate_limit_requests:
        return JSONResponse(status_code=429, content={"detail": "Too many requests"}, headers={"Retry-After": str(_rate_limit_window)})
    history.append(now)
    return await call_next(request)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


# ── Health check ──────────────────────────────────────────
@app.get("/api/health")
def health():
    try:
        latex_compiler = DocumentService().verify_compiler()
        return {"status": "ok", "latex_compiler": latex_compiler}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "degraded", "error": "LaTeX compiler unavailable"})


@app.get("/metrics")
def metrics_endpoint():
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(metrics.prometheus(), media_type="text/plain; version=0.0.4")


@app.get("/api/events/{generation_id}")
def pipeline_events(generation_id: str):
    """Read-only in-memory execution timeline for one generation."""
    return {"events": get_events(generation_id)}


from tools.extractors import extract_urls, build_extraction_diagnostics, repair_extracted_text

# ── Step 1: Extract text from uploaded file ───────────────
@app.post("/api/extract")
async def extract(file: UploadFile = File(...)):
    try:
        filename = (file.filename or "").lower()
        if not filename.endswith((".pdf", ".docx", ".txt")):
            raise HTTPException(status_code=415, detail="Only PDF, DOCX, and TXT files are supported")
        chunks = []
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="File too large (max 10MB)")
            chunks.append(chunk)
        content = b"".join(chunks)
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        if filename.endswith(".pdf") and not content.startswith(b"%PDF"):
            raise HTTPException(status_code=415, detail="Invalid PDF file")
        if filename.endswith(".docx") and not content.startswith(b"PK"):
            raise HTTPException(status_code=415, detail="Invalid DOCX file")
        raw_text = await asyncio.to_thread(get_pipeline_service().extract, content, file.filename)
        text = repair_extracted_text(raw_text)
        urls = extract_urls(text, content, file.filename)
        diagnostics = build_extraction_diagnostics(text, urls, content, file.filename)
        return JSONResponse(content={
            "extracted_text": text,
            "raw_extracted_text": raw_text,
            "filename": file.filename,
            "extracted_links": urls,
            "extraction_diagnostics": diagnostics,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Extraction failed")
        raise HTTPException(status_code=500, detail="Extraction failed")


# ── Step 2: Clean + Enrich extracted text ────────────────
@app.post("/api/clean")
async def clean(payload: CleanRequest):
    """Structures raw CV text into JSON and, when portfolio links are provided,
    enriches the profile with live verified evidence immediately.

    The returned ``enrichment_data`` and ``source_status`` give the UI real-time
    per-source feedback instead of silently dropping un-fetchable links.
    """
    try:
        if not payload.extracted_text.strip():
            raise HTTPException(status_code=400, detail="No extracted_text provided")

        cleaned = await asyncio.to_thread(get_pipeline_service().structure, payload.extracted_text)
        enrichment = CandidateEvidenceModel()
        if payload.portfolio_links:
            enrichment = await asyncio.to_thread(
                get_pipeline_service().enrich, payload.portfolio_links
            )
        return JSONResponse(content={
            "cleaned_data": cleaned.model_dump(mode="json"),
            "enrichment_data": [chunk.raw for chunk in enrichment.chunks],
            "source_status": [source.model_dump(mode="json") for source in enrichment.sources],
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Cleaning failed")
        raise HTTPException(status_code=500, detail="Cleaning failed")


# ── Step 2.5: Analyze job description (ATS Checker) ──────
@app.post("/api/analyze")
async def analyze(payload: AnalyzeRequest):
    try:
        if not payload.job_description.strip():
            raise HTTPException(status_code=400, detail="No job_description provided")
        if len(payload.job_description.strip()) < 20:
            raise HTTPException(status_code=400, detail="Job description too short (min 20 characters)")
        analysis = await asyncio.to_thread(get_pipeline_service().analyze, payload.job_description)
        return JSONResponse(content={"analysis": analysis.model_dump(mode="json")})
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# ── Step 2.6: ATS compatibility check — Dedicated Agentic Auditor ──────────
@app.post("/api/ats-check")
async def ats_check(payload: ATSCheckRequest):
    """
    Feature 2: Agentic ATS Resume Auditor.
    Runs the dedicated ats_auditor_agent crew to produce a comprehensive
    ATS compatibility report with score, keyword analysis, section feedback,
    and actionable rewrite recommendations. When portfolio links are provided,
    verified external evidence is fetched and fed into the audit so GitHub
    projects can influence the score.
    """
    try:
        if not payload.job_description.strip():
            raise HTTPException(status_code=400, detail="No job_description provided")
        if not payload.enriched_data:
            raise HTTPException(status_code=400, detail="No enriched_data provided")

        evidence = CandidateEvidenceModel()
        if payload.portfolio_links:
            evidence = await asyncio.to_thread(
                get_pipeline_service().enrich, payload.portfolio_links
            )

        report = await asyncio.to_thread(
            get_pipeline_service().audit,
            payload.enriched_data,
            payload.job_description,
            None,
            evidence,
        )
        return JSONResponse(content={
            **report.model_dump(mode="json"),
            "enrichment_data": [chunk.raw for chunk in evidence.chunks],
            "source_status": [source.model_dump(mode="json") for source in evidence.sources],
        })
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"ATS audit failed: {str(e)}")


@app.post("/api/ats-gap-inquire")
async def ats_gap_inquire(payload: GapInquireRequest):
    """
    Agentic Feedback Loop:
    Ingests candidate's answers about unlisted domain experience (e.g. "I used Power BI for Udemy analytics"),
    merges it into enriched_data notes, and re-runs the ATS auditor crew for instant recalibration.
    """
    try:
        if not payload.job_description.strip():
            raise HTTPException(status_code=400, detail="No job_description provided")
        if not payload.enriched_data:
            raise HTTPException(status_code=400, detail="No enriched_data provided")

        # Ingest candidate's gap answer if provided
        data = payload.enriched_data
        if payload.unlisted_experience.strip():
            notes = f"CANDIDATE DISCOVERED EXPERIENCE (merge into relevant skills/summary):\n{payload.unlisted_experience.strip()}"
            data = (await asyncio.to_thread(get_pipeline_service().structure, json.dumps(data), notes)).model_dump(mode="json")

        # Analyze the JD once and reuse the validated result for the audit and
        # deterministic inquiry-question synthesis.
        jd_analysis = await asyncio.to_thread(get_pipeline_service().analyze, payload.job_description)
        report = (await asyncio.to_thread(
            get_pipeline_service().audit,
            data,
            payload.job_description,
            jd_analysis,
        )).model_dump(mode="json")

        # Deterministic post-processing: typed, canonical, deduplicated questions
        # and grounded suggestions (never tells the user to claim unverified skills).
        report_model = postprocess_ats_report(
            ATSReport.model_validate(report), Candidate.model_validate(data), jd_analysis
        )
        report = report_model.model_dump(mode="json")

        report["recalibrated_data"] = data
        return JSONResponse(content=report)
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Gap inquiry recalibration failed: {str(e)}")



# ── Step 3: Generate from cleaned data (no re-extraction) ──
@app.post("/api/generate")
async def generate(payload: GenerateRequest):
    try:
        context = current_context()
        context.generation_id = f"gen_{uuid4().hex[:12]}"
        context.pipeline_id = context.generation_id
        emit_event("generation", "started", output_type=payload.output_type)
        if not payload.cleaned_data:
            raise HTTPException(status_code=400, detail="No cleaned_data provided")
        if not payload.job_description.strip():
            raise HTTPException(status_code=400, detail="No job_description provided")

        # Fail fast before spending time on LLM calls if LaTeX is unavailable.
        await asyncio.to_thread(DocumentService().verify_compiler)
        result = await asyncio.to_thread(
            get_generation_service().generate,
            payload.cleaned_data,
            payload.job_description,
            payload.output_type,
            payload.notes,
            payload.portfolio_links,
        )
        generated_files = [result[key] for key in ("cv_pdf", "cover_letter_pdf") if result.get(key)]
        return JSONResponse(content={
            "cv_pdf": result.get("cv_pdf"),
            "cover_letter_pdf": result.get("cover_letter_pdf"),
            "cleaned_data": result.get("cleaned_data"),
            "ats_report": result.get("ats_report"),
            "cover_letter_review": result.get("cover_letter_review"),
            "enrichment_data": result.get("enrichment_data", []),
            "source_status": result.get("source_status", []),
            "warnings": result.get("warnings", []),
            "document_token": result.get("document_token") or create_document_token(generated_files),
            "request_id": context.request_id,
            "generation_id": context.generation_id,
        })
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.exception("Generation failed")
        raise HTTPException(status_code=500, detail="Generation failed")


# ── Preview PDF in browser ───────────────────────────────
@app.get("/api/preview/{filename}")
async def preview(filename: str, token: str | None = Query(None)):
    if not SAFE_FILENAME.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    pdf_path = OUTPUT_DIR / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    if not token or not validate_document_token(token, filename):
        raise HTTPException(status_code=403, detail="Document access denied")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        content_disposition_type="inline",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# ── Download PDF ──────────────────────────────────────────
@app.get("/api/download/{filename}")
async def download(filename: str, token: str | None = Query(None)):
    if not SAFE_FILENAME.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    pdf_path = OUTPUT_DIR / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    if not token or not validate_document_token(token, filename):
        raise HTTPException(status_code=403, detail="Document access denied")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    reload_enabled = os.getenv("RELOAD", "false").lower() in {"1", "true", "yes"}
    uvicorn.run("main:app", host=host, port=port, reload=reload_enabled)
