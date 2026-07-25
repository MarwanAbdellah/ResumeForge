import os
import json
import re
import tempfile
from pathlib import Path

from xhtml2pdf import pisa

from crewai import Agent, Task, Crew, Process

from tools.extractors import extract_text
from tools.nvidia_nim import NvidiaNimLLM

# ── LLM setup: custom requests wrapper for NVIDIA NIM + diffusiongemma ──
llm = NvidiaNimLLM(
    model="nvidia-nim/diffusiongemma",
    api_key=os.getenv("NVIDIA_NIM_API_KEY"),
    nim_model="google/diffusiongemma-26b-a4b-it",
    nim_temperature=1.0,
    nim_top_p=0.95,
    nim_enable_thinking=True,
    nim_timeout=120,
    temperature=1.0,
    max_tokens=4096,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ══════════════════════════════════════════════════════════
#  AGENTS
# ══════════════════════════════════════════════════════════

extractor_agent = Agent(
    role="CV Text Extractor",
    goal="Extract all text content from an uploaded CV file (PDF or DOCX) accurately.",
    backstory=(
        "You are a document parsing specialist. Your job is to pull raw text "
        "from CV files while preserving structure like sections, bullet points, "
        "and contact information. You never summarize — you extract verbatim."
    ),
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

cleaner_agent = Agent(
    role="CV Data Cleaner",
    goal="Parse raw CV text into a clean, structured JSON with standard fields.",
    backstory=(
        "You are a data normalization expert. You take raw extracted text from a CV "
        "and parse it into a well-structured JSON object. You identify names, emails, "
        "phone numbers, work experience, education, skills, and projects. You preserve "
        "all details accurately and never fabricate information."
    ),
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

cv_generator_agent = Agent(
    role="ATS-Friendly CV Generator",
    goal="Generate a professional, ATS-optimized HTML CV tailored to a specific job description.",
    backstory=(
        "You are an expert resume writer. You take structured candidate data and a "
        "job description, then produce a single-column, ATS-friendly HTML document. "
        "You match keywords from the job description, quantify achievements, and "
        "ensure the CV is clean, professional, and passes ATS screening. "
        "You use the exact HTML template structure provided to you."
    ),
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

cover_letter_agent = Agent(
    role="Cover Letter Writer",
    goal="Generate a professional, tailored HTML cover letter for a specific job application.",
    backstory=(
        "You are an expert cover letter writer. You take structured candidate data "
        "and a job description, then produce a formal, compelling HTML cover letter. "
        "The letter includes: sender address, date, recipient address, a strong opening "
        "paragraph, a body that connects the candidate's experience to the role, and a "
        "professional closing. You use the exact HTML template structure provided."
    ),
    llm=llm,
    verbose=True,
    allow_delegation=False,
)


# ══════════════════════════════════════════════════════════
#  TASK FUNCTIONS (called by FastAPI)
# ══════════════════════════════════════════════════════════

def run_extraction(file_bytes: bytes, filename: str) -> str:
    """Task 1: Extract text from uploaded file."""
    return extract_text(file_bytes, filename)


def run_cleaning(raw_text: str) -> dict:
    """Task 2: Clean and structure the extracted text via LLM."""
    task = Task(
        description=(
            f"Parse the following raw CV text into a structured JSON object.\n\n"
            f"RAW TEXT:\n{raw_text}\n\n"
            f"Output ONLY valid JSON with these fields:\n"
            f'{{"name": "", "email": "", "phone": "", "location": "", '
            f'"summary": "", '
            f'"experience": [{{"title": "", "company": "", "location": "", "dates": "", "bullets": [""]}}], '
            f'"education": [{{"school": "", "degree": "", "field": "", "dates": "", "details": ""}}], '
            f'"skills": {{"languages": [], "tools": []}}, '
            f'"projects": [{{"name": "", "description": "", "bullets": [""]}}]}}'
        ),
        expected_output="A valid JSON object with structured CV data.",
        agent=cleaner_agent,
    )
    crew = Crew(agents=[cleaner_agent], tasks=[task], process=Process.sequential, verbose=True, tracing=True)
    try:
        result = crew.kickoff()
    except Exception as e:
        raise RuntimeError(f"Cleaning crew failed: {e}")

    raw = result.raw.strip() if result.raw else ""
    print(f"[Cleaning] Raw output length: {len(raw)}")
    if not raw and result.tasks_output:
        for task_output in result.tasks_output:
            if task_output.raw:
                raw = task_output.raw.strip()
                print(f"[Cleaning] Got raw from task_output, length: {len(raw)}")
                break
    if not raw:
        raise RuntimeError("Cleaning crew returned empty output")

    json_str = raw
    if "```" in json_str:
        parts = json_str.split("```")
        if len(parts) >= 3:
            json_str = parts[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
            json_str = json_str.strip()

    if not json_str.startswith("{"):
        match = re.search(r"\{.*\}", json_str, re.DOTALL)
        if match:
            json_str = match.group(0)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        open_braces = json_str.count("{") - json_str.count("}")
        open_brackets = json_str.count("[") - json_str.count("]")
        fixed = json_str + "]" * max(0, open_brackets) + "}" * max(0, open_braces)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

    raise RuntimeError(
        f"Failed to parse cleaned data as JSON.\n"
        f"First 300 chars: {json_str[:300]}\n"
        f"Last 300 chars: {json_str[-300:]}"
    )


def _extract_html(raw: str, start_tag: str = "<!DOCTYPE") -> str:
    """Extract HTML from LLM output, stripping markdown wrappers."""
    html = raw.strip()
    if "```" in html:
        parts = html.split("```")
        if len(parts) >= 3:
            html = parts[1]
            if html.startswith("html"):
                html = html[4:]
            html = html.strip()
    if not html.lower().startswith("<!doctype") and not html.lower().startswith("<html"):
        match = re.search(r"(<!DOCTYPE.*?</html>)", html, re.DOTALL | re.IGNORECASE)
        if match:
            html = match.group(1)
        else:
            # Try to find just the body content
            match = re.search(r"<body[^>]*>(.*)</body>", html, re.DOTALL | re.IGNORECASE)
            if match:
                html = f"<!DOCTYPE html><html><head><meta charset='UTF-8'></head><body>{match.group(1)}</body></html>"
    return html


def run_cv_generation(cleaned_data: dict, job_description: str) -> str:
    """Task 3: Generate ATS-friendly HTML CV."""
    template = (TEMPLATES_DIR / "cv_template.html").read_text(encoding="utf-8")
    task = Task(
        description=(
            "You are given an HTML/CSS CV template and structured candidate data.\n\n"
            f"HTML TEMPLATE:\n{template}\n\n"
            f"CANDIDATE DATA (JSON):\n{json.dumps(cleaned_data, indent=2)}\n\n"
            f"JOB DESCRIPTION:\n{job_description}\n\n"
            "Generate a complete HTML document that:\n"
            "1. Uses the EXACT same CSS classes and structure as the template\n"
            "2. Fills in all placeholders with the candidate's real data\n"
            "3. Tailors bullet points to match keywords from the job description\n"
            "4. Quantifies achievements where possible\n"
            "5. Keeps the single-column ATS-friendly format\n"
            "6. Skips sections that have no data (e.g. if experience is empty, omit the Experience section)\n\n"
            "Output ONLY the complete HTML source code, nothing else."
        ),
        expected_output="Complete HTML source code for the CV.",
        agent=cv_generator_agent,
    )
    crew = Crew(agents=[cv_generator_agent], tasks=[task], process=Process.sequential, verbose=True, tracing=True)
    try:
        result = crew.kickoff()
    except Exception as e:
        raise RuntimeError(f"CV generation crew failed: {e}")
    html = result.raw.strip() if result.raw else ""
    if not html and result.tasks_output:
        for task_output in result.tasks_output:
            if task_output.raw:
                html = task_output.raw.strip()
                break
    if not html:
        raise RuntimeError("CV generation crew returned empty output")
    html = _extract_html(html)
    if "<html" not in html.lower() and "<body" not in html.lower():
        raise RuntimeError(f"CV generator did not return valid HTML.\nOutput starts with: {html[:200]}")
    return html


def run_cover_letter_generation(cleaned_data: dict, job_description: str) -> str:
    """Task 4: Generate tailored HTML cover letter."""
    template = (TEMPLATES_DIR / "cover_letter_template.html").read_text(encoding="utf-8")
    task = Task(
        description=(
            "You are given an HTML/CSS cover letter template and structured candidate data.\n\n"
            f"HTML TEMPLATE:\n{template}\n\n"
            f"CANDIDATE DATA (JSON):\n{json.dumps(cleaned_data, indent=2)}\n\n"
            f"JOB DESCRIPTION:\n{job_description}\n\n"
            "Generate a complete HTML cover letter that:\n"
            "1. Uses the EXACT same CSS classes and structure as the template\n"
            "2. Fills in sender address from candidate data (use name, email, phone, location)\n"
            "3. Sets a current date\n"
            "4. Infers recipient details from the job description (company name, title)\n"
            "5. Writes a strong 3-paragraph body:\n"
            "   - Introduction: state the role and why you are applying\n"
            "   - Fit: connect candidate's experience to job requirements with specific examples\n"
            "   - Closing: express enthusiasm and call to action\n"
            "6. Uses formal tone throughout\n\n"
            "Output ONLY the complete HTML source code, nothing else."
        ),
        expected_output="Complete HTML source code for the cover letter.",
        agent=cover_letter_agent,
    )
    crew = Crew(agents=[cover_letter_agent], tasks=[task], process=Process.sequential, verbose=True, tracing=True)
    try:
        result = crew.kickoff()
    except Exception as e:
        raise RuntimeError(f"Cover letter generation crew failed: {e}")
    html = result.raw.strip() if result.raw else ""
    if not html and result.tasks_output:
        for task_output in result.tasks_output:
            if task_output.raw:
                html = task_output.raw.strip()
                break
    if not html:
        raise RuntimeError("Cover letter generation crew returned empty output")
    html = _extract_html(html)
    if "<html" not in html.lower() and "<body" not in html.lower():
        raise RuntimeError(f"Cover letter generator did not return valid HTML.\nOutput starts with: {html[:200]}")
    return html


def run_compilation(html_source: str, output_name: str) -> Path:
    """Task 5: Convert HTML to PDF using xhtml2pdf."""
    final_path = OUTPUT_DIR / f"{output_name}.pdf"
    try:
        with open(final_path, "wb") as f:
            status = pisa.CreatePDF(html_source, dest=f)
            if status.err:
                raise RuntimeError(f"xhtml2pdf conversion failed with {status.err} errors")
    except Exception as e:
        raise RuntimeError(f"PDF generation failed: {e}")
    if not final_path.exists() or final_path.stat().st_size == 0:
        raise RuntimeError("PDF was not generated or is empty.")
    return final_path


# ══════════════════════════════════════════════════════════
#  MAIN CREW RUNNERS
# ══════════════════════════════════════════════════════════

def run_generation_only(
    cleaned_data: dict,
    job_description: str,
    output_type: str,  # "cv" | "cover_letter" | "both"
) -> dict:
    """
    Generation pipeline only: generate -> compile.
    Assumes extraction and cleaning are already done.
    Returns dict with paths to generated PDFs.
    """
    import uuid
    run_id = uuid.uuid4().hex[:8]
    results = {}

    if output_type in ("cv", "both"):
        print("[Generation] Starting CV generation...")
        cv_html = run_cv_generation(cleaned_data, job_description)
        print("[Generation] CV HTML generated, converting to PDF...")
        cv_pdf = run_compilation(cv_html, f"cv_{run_id}")
        results["cv_pdf"] = str(cv_pdf)
        results["cv_html"] = cv_html
        print(f"[Generation] CV PDF created: {cv_pdf}")

    if output_type in ("cover_letter", "both"):
        print("[Generation] Starting cover letter generation...")
        cl_html = run_cover_letter_generation(cleaned_data, job_description)
        print("[Generation] Cover letter HTML generated, converting to PDF...")
        cl_pdf = run_compilation(cl_html, f"cover_letter_{run_id}")
        results["cover_letter_pdf"] = str(cl_pdf)
        results["cover_letter_html"] = cl_html
        print(f"[Generation] Cover letter PDF created: {cl_pdf}")

    results["cleaned_data"] = cleaned_data
    return results


def run_crew(
    file_bytes: bytes,
    filename: str,
    job_description: str,
    output_type: str,  # "cv" | "cover_letter" | "both"
) -> dict:
    """
    Full pipeline: extract -> clean -> generate -> compile.
    Returns dict with paths to generated PDFs.
    """
    raw_text = run_extraction(file_bytes, filename)
    cleaned = run_cleaning(raw_text)
    results = run_generation_only(cleaned, job_description, output_type)
    results["extracted_text"] = raw_text
    return results
