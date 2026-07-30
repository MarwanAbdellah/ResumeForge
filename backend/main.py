import os
import re
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from crew import run_extraction, run_cleaning, run_generation_only, run_jd_analysis, run_ats_checker_crew, run_structuring
from tools.link_fetcher import fetch_portfolio_links

app = FastAPI(title="ResumeForge API", version="1.0.0")

SAFE_FILENAME = re.compile(r"^[\w\-]+\.pdf$")


class CleanRequest(BaseModel):
    extracted_text: str
    portfolio_links: list[str] = []


class GenerateRequest(BaseModel):
    cleaned_data: dict
    job_description: str
    output_type: str = "both"
    notes: str = ""
    portfolio_links: list[str] = []


class AnalyzeRequest(BaseModel):
    job_description: str


class ATSCheckRequest(BaseModel):
    job_description: str
    enriched_data: dict

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.up\.railway\.app|https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


# ── Health check ──────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok"}


from tools.extractors import extract_urls

# ── Step 1: Extract text from uploaded file ───────────────
@app.post("/api/extract")
async def extract(file: UploadFile = File(...)):
    try:
        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large (max 10MB)")
        text = await asyncio.to_thread(run_extraction, content, file.filename)
        urls = extract_urls(text, content, file.filename)
        return JSONResponse(content={
            "extracted_text": text,
            "filename": file.filename,
            "extracted_links": urls,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


# ── Step 2: Clean + Enrich extracted text ────────────────
@app.post("/api/clean")
async def clean(payload: CleanRequest):
    """
    Structures raw CV text into JSON. If portfolio_links are provided,
    fetches live GitHub API data and passes it to the structuring agent
    for automatic project enrichment.
    """
    try:
        if not payload.extracted_text.strip():
            raise HTTPException(status_code=400, detail="No extracted_text provided")

        # Fetch enriched profile data from GitHub API if links provided
        enriched_profile = None
        if payload.portfolio_links:
            profiles = await asyncio.to_thread(fetch_portfolio_links, payload.portfolio_links)
            # Find the first GitHub profile result (richest data source)
            github_profiles = [p for p in profiles if p.get("platform") == "github" and p.get("github_user_info")]
            if github_profiles:
                enriched_profile = github_profiles[0]
            elif profiles:
                enriched_profile = profiles[0]  # Fall back to first enriched profile

        cleaned = await asyncio.to_thread(
            run_structuring,
            payload.extracted_text,
            "",            # notes (none at clean stage)
            enriched_profile,
        )
        return JSONResponse(content={"cleaned_data": cleaned})
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Cleaning failed: {str(e)}")


# ── Step 2.5: Analyze job description (ATS Checker) ──────
@app.post("/api/analyze")
async def analyze(payload: AnalyzeRequest):
    try:
        if not payload.job_description.strip():
            raise HTTPException(status_code=400, detail="No job_description provided")
        if len(payload.job_description.strip()) < 20:
            raise HTTPException(status_code=400, detail="Job description too short (min 20 characters)")
        analysis = await asyncio.to_thread(run_jd_analysis, payload.job_description)
        return JSONResponse(content={"analysis": analysis})
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

        # Flatten the enriched CV data into plain text for the agent to evaluate
        cv_text_parts = []
        data = payload.enriched_data
        for field in ("name", "email", "phone", "location", "summary"):
            if data.get(field):
                cv_text_parts.append(str(data[field]))
        for exp in data.get("experience", []) or []:
            for key in ("title", "company", "location", "dates"):
                if exp.get(key):
                    cv_text_parts.append(str(exp[key]))
            for bullet in exp.get("bullets", []) or []:
                cv_text_parts.append(str(bullet))
        for edu in data.get("education", []) or []:
            for key in ("school", "degree", "field", "dates", "details"):
                if edu.get(key):
                    cv_text_parts.append(str(edu[key]))
        skills = data.get("skills", {})
        if isinstance(skills, dict):
            for v in skills.values():
                if isinstance(v, list):
                    cv_text_parts.extend(str(s) for s in v)
        for proj in data.get("projects", []) or []:
            for key in ("name", "description"):
                if proj.get(key):
                    cv_text_parts.append(str(proj[key]))
            for bullet in proj.get("bullets", []) or []:
                cv_text_parts.append(str(bullet))
        for cert in data.get("certifications", []) or []:
            for v in cert.values():
                if v:
                    cv_text_parts.append(str(v))

        cv_text = "\n".join(cv_text_parts)

        # Run the dedicated ATS auditor crew
        report = await asyncio.to_thread(run_ats_checker_crew, cv_text, payload.job_description)
        return JSONResponse(content=report)
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
            data = await asyncio.to_thread(run_structuring, json.dumps(data), notes)

        # Run re-audit
        cv_text_parts = []
        for field in ("name", "email", "phone", "location", "summary"):
            if data.get(field):
                cv_text_parts.append(str(data[field]))
        for exp in data.get("experience", []) or []:
            for key in ("title", "company", "location", "dates"):
                if exp.get(key):
                    cv_text_parts.append(str(exp[key]))
            for bullet in exp.get("bullets", []) or []:
                cv_text_parts.append(str(bullet))
        for edu in data.get("education", []) or []:
            for key in ("school", "degree", "field", "dates", "details"):
                if edu.get(key):
                    cv_text_parts.append(str(edu[key]))
        skills = data.get("skills", {})
        if isinstance(skills, dict):
            for v in skills.values():
                if isinstance(v, list):
                    cv_text_parts.extend(str(s) for s in v)
        for proj in data.get("projects", []) or []:
            for key in ("name", "description"):
                if proj.get(key):
                    cv_text_parts.append(str(proj[key]))
            for bullet in proj.get("bullets", []) or []:
                cv_text_parts.append(str(bullet))

        cv_text = "\n".join(cv_text_parts)
        report = await asyncio.to_thread(run_ats_checker_crew, cv_text, payload.job_description)

        # Fallback question synthesizer for unlisted skills against target JD
        try:
            jd_analysis = await asyncio.to_thread(run_jd_analysis, payload.job_description)
            req_skills = (jd_analysis.get("required_skills") or []) + (jd_analysis.get("technical_stack") or [])

            cand_skills_flat = set()
            for part in cv_text_parts:
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
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Gap inquiry recalibration failed: {str(e)}")



# ── Step 3: Generate from cleaned data (no re-extraction) ──
@app.post("/api/generate")
async def generate(payload: GenerateRequest):
    try:
        if not payload.cleaned_data:
            raise HTTPException(status_code=400, detail="No cleaned_data provided")
        if not payload.job_description.strip():
            raise HTTPException(status_code=400, detail="No job_description provided")

        result = await asyncio.to_thread(
            run_generation_only, payload.cleaned_data, payload.job_description, payload.output_type, payload.notes, payload.portfolio_links
        )
        return JSONResponse(content={
            "cv_pdf": result.get("cv_pdf"),
            "cover_letter_pdf": result.get("cover_letter_pdf"),
            "cleaned_data": result.get("cleaned_data"),
            "ats_report": result.get("ats_report"),
        })
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


# ── Preview PDF in browser ───────────────────────────────
@app.get("/api/preview/{filename}")
async def preview(filename: str):
    if not SAFE_FILENAME.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    pdf_path = OUTPUT_DIR / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        content_disposition_type="inline",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# ── Download PDF ──────────────────────────────────────────
@app.get("/api/download/{filename}")
async def download(filename: str):
    if not SAFE_FILENAME.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    pdf_path = OUTPUT_DIR / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
