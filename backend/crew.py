import os
import json
import re
import subprocess
import tempfile
import shutil
from pathlib import Path

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


def sanitize_latex(text: str) -> str:
    """Escape special LaTeX characters in user-provided text."""
    if not isinstance(text, str):
        return text
    # Order matters: backslash first
    text = text.replace("\\", "\\textbackslash{}")
    text = text.replace("{", "\\{").replace("}", "\\}")
    text = text.replace("\\textbackslash\\{\\}", "\\textbackslash{}")
    text = text.replace("&", "\\&")
    text = text.replace("%", "\\%")
    text = text.replace("#", "\\#")
    text = text.replace("_", "\\_")
    text = text.replace("~", "\\textasciitilde{}")
    text = text.replace("^", "\\textasciicircum{}")
    text = text.replace("$", "\\$")
    return text


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
    goal="Generate a professional, ATS-optimized LaTeX CV tailored to a specific job description.",
    backstory=(
        "You are an expert resume writer and LaTeX typographer. You take structured "
        "candidate data and a job description, then produce a single-column, ATS-friendly "
        "LaTeX document. You match keywords from the job description, quantify achievements, "
        "and ensure the CV is clean, professional, and passes ATS screening. "
        "You use the exact LaTeX template structure provided to you."
    ),
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

cover_letter_agent = Agent(
    role="Cover Letter Writer",
    goal="Generate a professional, tailored LaTeX cover letter for a specific job application.",
    backstory=(
        "You are an expert cover letter writer. You take structured candidate data "
        "and a job description, then produce a formal, compelling LaTeX cover letter. "
        "The letter includes: sender address, date, recipient address, a strong opening "
        "paragraph, a body that connects the candidate's experience to the role, and a "
        "professional closing. You use the exact LaTeX template structure provided."
    ),
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

compiler_agent = Agent(
    role="LaTeX Compiler",
    goal="Compile LaTeX source code into a PDF file using pdflatex.",
    backstory=(
        "You are a LaTeX compilation specialist. You take LaTeX source code, write it "
        "to a .tex file, run pdflatex to compile it, and return the path to the "
        "generated PDF. You handle errors gracefully and ensure the output is clean."
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
    raw = result.raw.strip()
    # Extract JSON from possible markdown code blocks
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse cleaned data as JSON: {e}\nRaw output: {raw[:500]}")


def run_cv_generation(cleaned_data: dict, job_description: str) -> str:
    """Task 3: Generate ATS-friendly LaTeX CV."""
    template = (TEMPLATES_DIR / "cv_template.tex").read_text(encoding="utf-8")
    task = Task(
        description=(
            "You are given a LaTeX CV template and structured candidate data.\n\n"
            f"LATEX TEMPLATE:\n{template}\n\n"
            f"CANDIDATE DATA (JSON):\n{json.dumps(cleaned_data, indent=2)}\n\n"
            f"JOB DESCRIPTION:\n{job_description}\n\n"
            "Generate a complete, compilable LaTeX document that:\n"
            "1. Uses the EXACT template structure and custom commands (\\expentry, \\eduentry, \\projentry)\n"
            "2. Fills in all placeholders with the candidate's real data\n"
            "3. Tailors bullet points to match keywords from the job description\n"
            "4. Quantifies achievements where possible\n"
            "5. Keeps the single-column ATS-friendly format\n"
            "6. Escapes special LaTeX characters (percent, ampersand, hash, underscore, braces) in user text\n\n"
            "Output ONLY the complete LaTeX source code, nothing else."
        ),
        expected_output="Complete compilable LaTeX source code for the CV.",
        agent=cv_generator_agent,
    )
    crew = Crew(agents=[cv_generator_agent], tasks=[task], process=Process.sequential, verbose=True, tracing=True)
    try:
        result = crew.kickoff()
    except Exception as e:
        raise RuntimeError(f"CV generation crew failed: {e}")
    latex = result.raw.strip()
    # Strip markdown code block wrappers if present
    if latex.startswith("```"):
        latex = re.sub(r"^```\w*\n?", "", latex)
        latex = re.sub(r"\n?```$", "", latex)
    if not latex.strip().startswith("\\documentclass"):
        raise RuntimeError(f"CV generator did not return valid LaTeX.\nOutput starts with: {latex[:200]}")
    return latex


def run_cover_letter_generation(cleaned_data: dict, job_description: str) -> str:
    """Task 4: Generate tailored LaTeX cover letter."""
    template = (TEMPLATES_DIR / "cover_letter_template.tex").read_text(encoding="utf-8")
    task = Task(
        description=(
            "You are given a LaTeX cover letter template and structured candidate data.\n\n"
            f"LATEX TEMPLATE:\n{template}\n\n"
            f"CANDIDATE DATA (JSON):\n{json.dumps(cleaned_data, indent=2)}\n\n"
            f"JOB DESCRIPTION:\n{job_description}\n\n"
            "Generate a complete, compilable LaTeX cover letter that:\n"
            "1. Uses the EXACT template structure with all placeholder fields\n"
            "2. Fills in sender address from candidate data (use name, email, phone, location)\n"
            "3. Sets a current date\n"
            "4. Infers recipient details from the job description (company name, title)\n"
            "5. Writes a strong 3-paragraph body:\n"
            "   - Introduction: state the role and why you are applying\n"
            "   - Fit: connect candidate's experience to job requirements with specific examples\n"
            "   - Closing: express enthusiasm and call to action\n"
            "6. Uses formal tone throughout\n"
            "7. Escapes special LaTeX characters in user text\n\n"
            "Output ONLY the complete LaTeX source code, nothing else."
        ),
        expected_output="Complete compilable LaTeX source code for the cover letter.",
        agent=cover_letter_agent,
    )
    crew = Crew(agents=[cover_letter_agent], tasks=[task], process=Process.sequential, verbose=True, tracing=True)
    try:
        result = crew.kickoff()
    except Exception as e:
        raise RuntimeError(f"Cover letter generation crew failed: {e}")
    latex = result.raw.strip()
    if latex.startswith("```"):
        latex = re.sub(r"^```\w*\n?", "", latex)
        latex = re.sub(r"\n?```$", "", latex)
    if not latex.strip().startswith("\\documentclass"):
        raise RuntimeError(f"Cover letter generator did not return valid LaTeX.\nOutput starts with: {latex[:200]}")
    return latex


def run_compilation(latex_source: str, output_name: str) -> Path:
    """Task 5: Compile LaTeX to PDF."""
    # Find pdflatex: check PATH first, then common MiKTeX locations
    pdflatex_cmd = shutil.which("pdflatex")
    if not pdflatex_cmd:
        miktex_path = Path.home() / "AppData/Local/Programs/MiKTeX/miktex/bin/x64/pdflatex.exe"
        if miktex_path.exists():
            pdflatex_cmd = str(miktex_path)
        else:
            raise RuntimeError("pdflatex not found. Add MiKTeX to PATH or install it.")

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / f"{output_name}.tex"
        tex_path.write_text(latex_source, encoding="utf-8")

        # Run pdflatex twice for references
        for i in range(2):
            result = subprocess.run(
                [pdflatex_cmd, "-interaction=nonstopmode", "-halt-on-error",
                 "-output-directory", tmpdir, str(tex_path)],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                # Read the log file for detailed error info
                log_path = Path(tmpdir) / f"{output_name}.log"
                log_excerpt = ""
                if log_path.exists():
                    log_text = log_path.read_text(errors="replace")
                    # Find the error line
                    for line in log_text.split("\n"):
                        if line.startswith("!") or "error" in line.lower():
                            log_excerpt += line + "\n"
                    if not log_excerpt:
                        log_excerpt = log_text[-1500:]
                raise RuntimeError(
                    f"pdflatex failed on run {i+1}:\nSTDOUT:\n{result.stdout[-1000:]}\n"
                    f"STDERR:\n{result.stderr[-500:]}\nLOG ERRORS:\n{log_excerpt}"
                )

        pdf_path = Path(tmpdir) / f"{output_name}.pdf"
        if not pdf_path.exists():
            raise RuntimeError("PDF was not generated.")

        # Copy to output directory
        final_path = OUTPUT_DIR / f"{output_name}.pdf"
        final_path.write_bytes(pdf_path.read_bytes())
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
        cv_latex = run_cv_generation(cleaned_data, job_description)
        print("[Generation] CV LaTeX generated, compiling...")
        cv_pdf = run_compilation(cv_latex, f"cv_{run_id}")
        results["cv_pdf"] = str(cv_pdf)
        results["cv_latex"] = cv_latex
        print(f"[Generation] CV compiled: {cv_pdf}")

    if output_type in ("cover_letter", "both"):
        print("[Generation] Starting cover letter generation...")
        cl_latex = run_cover_letter_generation(cleaned_data, job_description)
        print("[Generation] Cover letter LaTeX generated, compiling...")
        cl_pdf = run_compilation(cl_latex, f"cover_letter_{run_id}")
        results["cover_letter_pdf"] = str(cl_pdf)
        results["cover_letter_latex"] = cl_latex
        print(f"[Generation] Cover letter compiled: {cl_pdf}")

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
    import uuid
    run_id = uuid.uuid4().hex[:8]

    # Step 1: Extract
    raw_text = run_extraction(file_bytes, filename)

    # Step 2: Clean
    cleaned = run_cleaning(raw_text)

    # Step 3+4+5: Generate and compile
    results = run_generation_only(cleaned, job_description, output_type)
    results["extracted_text"] = raw_text
    return results
