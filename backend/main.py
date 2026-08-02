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
from pydantic import BaseModel, Field
from typing import Literal
from security import create_document_token, validate_document_token
from services.document_service import DocumentService
from services.generation_service import GenerationService
from services.pipeline_service import PipelineService, flatten_candidate
from observability.context import bind_context, new_context, reset_context, current_context
from observability.events import emit_event
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


class CleanRequest(BaseModel):
    extracted_text: str = Field(min_length=1, max_length=100_000)
    portfolio_links: list[str] = Field(default_factory=list, max_length=10)


class GenerateRequest(BaseModel):
    cleaned_data: dict = Field(min_length=1)
    job_description: str = Field(min_length=1, max_length=50_000)
    output_type: Literal["cv", "cover_letter", "both"] = "both"
    notes: str = Field(default="", max_length=10_000)
    portfolio_links: list[str] = Field(default_factory=list, max_length=10)


class AnalyzeRequest(BaseModel):
    job_description: str = Field(min_length=10, max_length=50_000)


class ATSCheckRequest(BaseModel):
    job_description: str = Field(max_length=50_000)
    enriched_data: dict

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
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


from tools.extractors import extract_urls

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
        text = await asyncio.to_thread(get_pipeline_service().extract, content, file.filename)
        urls = extract_urls(text, content, file.filename)
        return JSONResponse(content={
            "extracted_text": text,
            "filename": file.filename,
            "extracted_links": urls,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Extraction failed")
        raise HTTPException(status_code=500, detail="Extraction failed")


# ── Step 2: Clean + Enrich extracted text ────────────────
@app.post("/api/clean")
async def clean(payload: CleanRequest):
    """Structures raw CV text into JSON.

    Portfolio enrichment is intentionally deferred until generation, after
    the job description has been analyzed and can drive repository ranking.
    """
    try:
        if not payload.extracted_text.strip():
            raise HTTPException(status_code=400, detail="No extracted_text provided")

        cleaned = await asyncio.to_thread(get_pipeline_service().structure, payload.extracted_text)
        return JSONResponse(content={"cleaned_data": cleaned.model_dump(mode="json"), "enrichment_data": []})
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
    and actionable rewrite recommendations.
    """
    try:
        if not payload.job_description.strip():
            raise HTTPException(status_code=400, detail="No job_description provided")
        if not payload.enriched_data:
            raise HTTPException(status_code=400, detail="No enriched_data provided")

        report = await asyncio.to_thread(get_pipeline_service().audit, payload.enriched_data, payload.job_description)
        return JSONResponse(content=report.model_dump(mode="json"))
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"ATS audit failed: {str(e)}")


class GapInquireRequest(BaseModel):
    job_description: str
    enriched_data: dict
    unlisted_experience: str = ""  # User's answer describing missing domain skills


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

        report = (await asyncio.to_thread(get_pipeline_service().audit, data, payload.job_description)).model_dump(mode="json")

        # Fallback question synthesizer for unlisted skills against target JD
        try:
            jd_analysis = await asyncio.to_thread(get_pipeline_service().analyze, payload.job_description)
            req_skills = jd_analysis.required_skills + jd_analysis.technical_stack

            cand_skills_flat = set()
            for part in flatten_candidate(data).splitlines():
                for token in re.split(r"[\s,;/\n]+", part.lower()):
                    if token.strip():
                        cand_skills_flat.add(token.strip())

            inquiry_questions = report.get("inquiry_questions") or []
            existing_kw = {q.get("keyword", "").lower() for q in inquiry_questions if isinstance(q, dict) and q.get("keyword")}

            for sk in req_skills:
                sk_clean = str(sk).strip()
                if sk_clean.lower() not in cand_skills_flat and sk_clean.lower() not in existing_kw and len(sk_clean) > 1:
                    inquiry_questions.append({
                        "keyword": sk_clean,
                        "question": f"The job description requires experience with {sk_clean}. Based on your extracted profile, {sk_clean} is unlisted. Have you ever worked with {sk_clean} or used {sk_clean} in any projects, labs, or coursework?"
                    })
                    existing_kw.add(sk_clean.lower())

            report["inquiry_questions"] = inquiry_questions
        except Exception as e:
            logger.warning(f"JD gap analysis fallback error: {e}")

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
            "enrichment_data": result.get("enrichment_data", []),
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
