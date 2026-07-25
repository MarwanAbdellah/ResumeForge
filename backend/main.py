import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from crew import run_extraction, run_cleaning, run_cv_generation, run_cover_letter_generation, run_compilation, run_crew, run_generation_only

app = FastAPI(title="ResumeForge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "https://*.vercel.app",
        "https://*.up.railway.app",
        "https://*.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Health check ──────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "nvidia_key_set": bool(os.getenv("NVIDIA_NIM_API_KEY"))}


# ── Step 1: Extract text from uploaded file ───────────────
@app.post("/api/extract")
async def extract(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = await asyncio.to_thread(run_extraction, content, file.filename)
        return JSONResponse(content={"extracted_text": text, "filename": file.filename})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


# ── Step 2: Clean extracted text ──────────────────────────
@app.post("/api/clean")
async def clean(payload: dict):
    try:
        raw_text = payload.get("extracted_text", "")
        if not raw_text:
            raise HTTPException(status_code=400, detail="No extracted_text provided")
        cleaned = await asyncio.to_thread(run_cleaning, raw_text)
        return JSONResponse(content={"cleaned_data": cleaned})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleaning failed: {str(e)}")


# ── Step 3: Generate from cleaned data (no re-extraction) ──
@app.post("/api/generate")
async def generate(payload: dict):
    try:
        cleaned_data = payload.get("cleaned_data")
        job_description = payload.get("job_description", "")
        output_type = payload.get("output_type", "both")

        if not cleaned_data:
            raise HTTPException(status_code=400, detail="No cleaned_data provided")
        if not job_description:
            raise HTTPException(status_code=400, detail="No job_description provided")

        result = await asyncio.to_thread(
            run_generation_only, cleaned_data, job_description, output_type
        )
        return JSONResponse(content={
            "cv_pdf": result.get("cv_pdf"),
            "cover_letter_pdf": result.get("cover_letter_pdf"),
            "cleaned_data": result.get("cleaned_data"),
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
    pdf_path = OUTPUT_DIR / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)


# ── Download PDF ──────────────────────────────────────────
@app.get("/api/download/{filename}")
async def download(filename: str):
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
