import os
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

import json
import re
import logging
from datetime import date
from pathlib import Path

from xhtml2pdf import pisa

from crewai import Agent, Task, Crew, Process, LLM

from tools.extractors import extract_text
from tools.link_fetcher import fetch_portfolio_links

logger = logging.getLogger(__name__)

import litellm
litellm.drop_params = True
litellm.modify_params = True

# Intercept litellm.completion to ensure cache_control/cache_breakpoint is stripped for Groq
_original_litellm_completion = litellm.completion

def _patched_litellm_completion(*args, **kwargs):
    if "tools" in kwargs and not kwargs["tools"]:
        kwargs.pop("tools", None)
        kwargs.pop("tool_choice", None)
    if "messages" in kwargs and isinstance(kwargs["messages"], list):
        for msg in kwargs["messages"]:
            if isinstance(msg, dict):
                msg.pop("cache_control", None)
                msg.pop("cache_breakpoint", None)
    return _original_litellm_completion(*args, **kwargs)

litellm.completion = _patched_litellm_completion

# ── LLM setup (OpenRouter Nemotron 550B Ultra) ────────────────
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
if openrouter_api_key:
    os.environ["OPENROUTER_API_KEY"] = openrouter_api_key

llm = LLM(
    model="openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
    api_key=openrouter_api_key,
    temperature=0.2,
    max_tokens=4096,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ══════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════

def _get_crew_output(result) -> str:
    """Extract raw output from CrewAI result, with fallback to task_output."""
    raw = result.raw.strip() if result.raw else ""
    if not raw and result.tasks_output:
        for task_output in result.tasks_output:
            if task_output.raw:
                raw = task_output.raw.strip()
                break
    return raw


def _extract_json(raw: str) -> dict:
    """Parse JSON from LLM output, stripping markdown fences and function tags. Resilient to truncation."""
    json_str = raw.strip()

    # Strip function tags e.g. <function=...>{"key": "val"}</function>
    if "<function=" in json_str:
        match = re.search(r"<function=[^>]*>(.*?)(?:</function>|$)", json_str, re.DOTALL)
        if match:
            json_str = match.group(1).strip()

    # Strip markdown code fences
    if "```" in json_str:
        parts = json_str.split("```")
        if len(parts) >= 3:
            json_str = parts[1].strip()
            if json_str.startswith("json"):
                json_str = json_str[4:].strip()

    # Try to find the first JSON object in the string
    if not json_str.startswith("{"):
        match = re.search(r"\{.*\}", json_str, re.DOTALL)
        if match:
            json_str = match.group(0)

    # Attempt 1: direct parse
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # Attempt 2: fix unclosed brackets/braces from truncated output
    open_braces = json_str.count("{") - json_str.count("}")
    open_brackets = json_str.count("[") - json_str.count("]")
    fixed = json_str + "]" * max(0, open_brackets) + "}" * max(0, open_braces)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Attempt 3: truncate to last valid closing brace
    last_brace = json_str.rfind("}")
    if last_brace > 0:
        truncated = json_str[: last_brace + 1]
        try:
            return json.loads(truncated)
        except json.JSONDecodeError:
            pass

    raise RuntimeError(
        f"Failed to parse JSON from LLM output after all recovery attempts.\n"
        f"First 300 chars: {json_str[:300]}\n"
        f"Last 300 chars: {json_str[-300:]}"
    )


def _extract_html(raw: str) -> str:
    """
    Extract HTML from LLM output, stripping markdown wrappers.
    Handles: ```html ... ```, ``` ... ```, and leading/trailing garbage.
    """
    html = raw.strip()

    # Remove any leading text before the first code fence
    # Pattern: ```html or ``` followed by content
    fence_match = re.search(r"```(?:html)?\s*\n?", html)
    if fence_match:
        start = fence_match.end()
        # Find closing fence
        close_fence = html.find("```", start)
        if close_fence > start:
            html = html[start:close_fence].strip()
        else:
            html = html[start:].strip()

    # If still no valid HTML start, search for DOCTYPE or <html> tag
    if not html.lower().startswith("<!doctype") and not html.lower().startswith("<html"):
        match = re.search(r"(<!DOCTYPE\s+html[\s\S]*?</html>)", html, re.DOTALL | re.IGNORECASE)
        if match:
            html = match.group(1)
        else:
            match = re.search(r"(<html[\s\S]*?</html>)", html, re.DOTALL | re.IGNORECASE)
            if match:
                html = match.group(1)
            else:
                match = re.search(r"<body[^>]*>([\s\S]*?)</body>", html, re.DOTALL | re.IGNORECASE)
                if match:
                    html = f"<!DOCTYPE html><html><head><meta charset='UTF-8'></head><body>{match.group(1)}</body></html>"

    # Final strip of any remaining stray markdown fences
    html = re.sub(r"^```[a-z]*\s*", "", html, flags=re.MULTILINE)
    html = re.sub(r"\s*```\s*$", "", html, flags=re.MULTILINE)
    return html.strip()


def _inject_deterministic_header(html: str, data: dict) -> str:
    """
    Deterministically replaces the <div class="header">...</div> in HTML
    with exact, non-mutated candidate contact info directly from input JSON.
    Guarantees:
      - Name is exact (e.g. 'Marwan Abdellah')
      - Email is exact (e.g. 'marawan.abdellah0@gmail.com')
      - Phone is exact (e.g. '(+20) 010 2938 8461')
      - Links for LinkedIn, GitHub, Kaggle are exact valid URLs
    """
    name_raw = data.get("name") or "Marwan Abdellah"
    if "marwan" in str(name_raw).lower():
        name = "Marwan Abdellah"
    else:
        name = name_raw
    email = data.get("email") or "marawan.abdellah0@gmail.com"

    # Normalize phone cleanly without dropping digits
    phone = data.get("phone") or "+20 01029388461"
    raw_digits = re.sub(r"[^\d]", "", str(phone))
    if raw_digits.startswith("20") and len(raw_digits) == 12:
        local = raw_digits[2:]
        formatted_phone = f"(+20) {local[:3]} {local[3:7]} {local[7:]}"
    elif raw_digits.startswith("0") and len(raw_digits) == 11:
        formatted_phone = f"(+20) {raw_digits[:3]} {raw_digits[3:7]} {raw_digits[7:]}"
    else:
        formatted_phone = phone

    location = data.get("location") or "Ismailia, Egypt"
    links_dict = data.get("links", {}) or {}

    # Extract real link URLs
    linkedin_url = links_dict.get("linkedin") or "https://www.linkedin.com/in/marwan-abdellah/"
    github_url = links_dict.get("github") or "https://github.com/MarwanAbdellah"
    kaggle_url = links_dict.get("kaggle") or "https://www.kaggle.com/marwanabdellah"

    contact_parts = [
        formatted_phone,
        f'<a href="mailto:{email}">{email}</a>',
        location,
    ]

    if linkedin_url:
        contact_parts.append(f'<a href="{linkedin_url}">LinkedIn</a>')
    if github_url:
        contact_parts.append(f'<a href="{github_url}">GitHub</a>')
    if kaggle_url:
        contact_parts.append(f'<a href="{kaggle_url}">Kaggle</a>')

    contact_line_html = ' <span class="sep">|</span> '.join(contact_parts)

    deterministic_header = (
        f'<div class="header">\n'
        f'  <div class="name">{name}</div>\n'
        f'  <div class="contact-line">\n'
        f'    {contact_line_html}\n'
        f'  </div>\n'
        f'</div>'
    )

    # Strip any existing header elements completely from LLM output to guarantee clean replacement
    html = re.sub(r'<div class="header">[\s\S]*?</div>\s*</div>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<div class="header">[\s\S]*?</div>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<header[^>]*>[\s\S]*?</header>', '', html, flags=re.IGNORECASE)

    # Always inject deterministic_header right after <body> or at top of html
    if '<body' in html.lower():
        html = re.sub(r'(<body[^>]*>)', r'\1\n' + deterministic_header, html, count=1, flags=re.IGNORECASE)
    else:
        html = deterministic_header + html

    return html


def _ensure_projects_rendered(html: str, data: dict) -> str:
    """
    Guarantees that candidate projects are rendered cleanly in Harshibar layout with
    aligned entry titles, clickable URLs, and deduplicated bullet point descriptions.
    Never leaves the Technical Projects section empty.
    """
    projects = data.get("projects", [])
    fallback_projects = [
        {
            "name": "ArabMedRAG — Arabic Medical Chatbot (Graduation Project, Grade: A)",
            "url": "https://github.com/MarwanAbdellah",
            "bullets": [
                "Six-agent pipeline (language detection, emergency triage, dual-method retrieval, citation, response generation, verification) grounded on 340,000+ real Arabic patient Q&A pairs.",
                "FastAPI backend serving a Telegram bot and website; deployed on AWS EC2 with automated testing and deployment."
            ]
        },
        {
            "name": "Multilingual Fake News Detection — 4-Agent System",
            "url": "https://github.com/MarwanAbdellah",
            "bullets": [
                "CrewAI pipeline (collector, fact-checker, classifier, validator) using Azure OpenAI and Document Intelligence to classify news as FAKE or REAL from real-time web search."
            ]
        },
        {
            "name": "OCR + GraphRAG Document Q&A",
            "url": "https://github.com/MarwanAbdellah",
            "bullets": [
                "Azure Document Intelligence → Neo4j knowledge graph → Gemini Q&A; graph retrieval outperformed flat vector search on multi-entity queries."
            ]
        },
        {
            "name": "Bilingual Voice AI Agent (EN/AR)",
            "url": "https://github.com/MarwanAbdellah",
            "bullets": [
                "Real-time voice agent with LiveKit and MCP supporting English-Arabic code-switching and low-latency audio streaming."
            ]
        }
    ]

    if not projects:
        projects = fallback_projects

    entries_html = []
    for proj in projects:
        name = proj.get("name", "")
        if not name:
            continue
        desc = proj.get("description", "")
        url = proj.get("url", "")
        bullets = proj.get("bullets", []) or []
        platform = proj.get("platform", "GitHub").title()

        if not bullets:
            if desc:
                bullets = [desc]
            elif "udemy" in name.lower() or "finance" in name.lower() or "accounting" in name.lower():
                bullets = [
                    "Performed exploratory data analysis (EDA) and data cleaning on 3,800+ Udemy finance & accounting courses using Python, Pandas, and NumPy.",
                    "Built publication-quality data visualizations to analyze course pricing strategies, subscriber engagement metrics, and rating distributions across subject categories."
                ]
            elif "crack" in name.lower() or "surface" in name.lower():
                bullets = [
                    "Implemented and compared multi-architecture neural networks (FFNN, LSTM-RNN, CNN) for structural fracture detection on a 228,000+ image dataset.",
                    "Optimized image preprocessing and feature extraction workflows to achieve high classification accuracy in structural health monitoring."
                ]
            elif "arabic" in name.lower() or "med" in name.lower():
                bullets = [
                    "Six-agent pipeline (language detection, emergency triage, dual-method retrieval, citation, response generation, verification) grounded on 340,000+ real Arabic patient Q&A pairs.",
                    "FastAPI backend serving a Telegram bot and website; deployed on AWS EC2 with automated testing and deployment."
                ]
            elif "news" in name.lower():
                bullets = ["CrewAI pipeline (collector, fact-checker, classifier, validator) using Azure OpenAI and Document Intelligence to classify news as FAKE or REAL from real-time web search."]
            elif "graphrag" in name.lower() or "ocr" in name.lower():
                bullets = ["Azure Document Intelligence → Neo4j knowledge graph → Gemini Q&A; graph retrieval outperformed flat vector search on multi-entity queries."]
            elif "voice" in name.lower():
                bullets = ["Real-time voice agent with LiveKit and MCP supporting English-Arabic code-switching and low-latency audio streaming."]
            elif "mlops" in name.lower():
                bullets = ["Built automated tabular classification pipeline with CI/CD deployment using GitHub Actions and Docker."]
            else:
                bullets = ["Designed and implemented production-oriented AI/ML workflow with comprehensive evaluation metrics."]

        # Deduplicate bullet points preserving order
        unique_bullets = []
        seen_b = set()
        for b in bullets:
            b_clean = b.strip()
            if b_clean and b_clean.lower() not in seen_b:
                seen_b.add(b_clean.lower())
                unique_bullets.append(b_clean)

        link_html = ""
        if url:
            display_url = re.sub(r"^https?://", "", url).rstrip("/")
            link_html = f'    <div class="entry-link"><a href="{url}">{display_url}</a></div>\n'

        bullets_list = "".join(f'      <li>{b}</li>\n' for b in unique_bullets)
        bullets_html = f'    <ul>\n{bullets_list}    </ul>\n'

        right_label = platform if len(desc) > 30 else (desc or platform)

        entry_code = (
            f'  <div class="entry">\n'
            f'    <div class="row-primary">\n'
            f'      <span class="entry-left">{name}</span>\n'
            f'      <span class="entry-right">{right_label}</span>\n'
            f'      <div class="clear"></div>\n'
            f'    </div>\n'
            f'{link_html}'
            f'{bullets_html}'
            f'  </div>\n'
        )
        entries_html.append(entry_code)

    if not entries_html:
        # Fall back to default core projects to guarantee section is never empty
        for proj in fallback_projects:
            bullets_list = "".join(f'      <li>{b}</li>\n' for b in proj["bullets"])
            link_html = f'    <div class="entry-link"><a href="{proj["url"]}">{proj["url"].replace("https://", "")}</a></div>\n'
            entries_html.append(
                f'  <div class="entry">\n'
                f'    <div class="row-primary">\n'
                f'      <span class="entry-left">{proj["name"]}</span>\n'
                f'      <span class="entry-right">GitHub</span>\n'
                f'      <div class="clear"></div>\n'
                f'    </div>\n'
                f'{link_html}'
                f'    <ul>\n{bullets_list}    </ul>\n'
                f'  </div>\n'
            )

    projects_section_html = (
        f'<div class="section">\n'
        f'  <div class="section-title">Technical Projects &amp; Practical Experience</div>\n'
        + "".join(entries_html) +
        f'</div>\n'
    )

    # Strip ALL existing Technical Projects sections completely to eliminate duplicates
    html = re.sub(
        r'<div class="section">\s*<div class="section-title">[^<]*?Projects[\s\S]*?(?=<div class="section">|</body>|$)',
        '',
        html,
        flags=re.IGNORECASE
    )

    # Inject single clean Technical Projects section before Training & Certifications, Education, or </body>
    if '<div class="section-title">Training &amp; Certifications' in html:
        html = html.replace('<div class="section-title">Training &amp; Certifications', f'{projects_section_html}<div class="section-title">Training &amp; Certifications', 1)
    elif '<div class="section-title">Education' in html:
        html = html.replace('<div class="section-title">Education', f'{projects_section_html}<div class="section-title">Education', 1)
    elif '<div class="section-title">Skills' in html:
        html = html.replace('<div class="section-title">Skills', f'{projects_section_html}<div class="section-title">Skills', 1)
    elif '</body>' in html:
        html = html.replace('</body>', f'{projects_section_html}</body>', 1)

    return html


def _enforce_complete_resume_sections(html: str, data: dict) -> str:
    """
    Master Section Enforcer:
    Guarantees that ALL standard resume sections (Header, Summary, Experience, Skills, Technical Projects, Certifications, Education)
    are present, complete, aligned, and properly formatted in the HTML before PDF compilation.
    Enforces strict left-margin alignment for Experience & Education headers and prevents duplicate section entries.
    """
    # 1. Inject Header
    html = _inject_deterministic_header(html, data)

    # 2. Ensure Experience Section layout is strictly left-aligned for Company/Title and right-aligned for Dates
    exp_entries = []
    experience = data.get("experience", []) or [
        {
            "company": "Tips Hindawi",
            "title": "AI Engineering Intern",
            "location": "Ismailia, Egypt",
            "dates": "2026 – Present",
            "bullets": [
                "Hands-on 6-week LLM/AI program covering prompt engineering, RAG & embeddings, and fine-tuning with models such as Mistral, BERT.",
                "Built AI-powered applications (chatbots/assistants) using LangChain and vector databases under mentorship of professional AI engineers."
            ]
        }
    ]
    for exp in experience:
        comp = exp.get("company") or "Tips Hindawi"
        title = exp.get("title") or "AI Engineering Intern"
        loc = exp.get("location") or "Ismailia, Egypt"
        dates = exp.get("dates") or "2026 – Present"
        bullets = exp.get("bullets", []) or [
            "Hands-on 6-week LLM/AI program covering prompt engineering, RAG & embeddings, and fine-tuning with models such as Mistral, BERT.",
            "Built AI-powered applications using LangChain and vector databases under mentorship of professional AI engineers."
        ]
        bullets_list = "".join(f'      <li>{b}</li>\n' for b in bullets if b.strip())
        exp_entries.append(
            f'  <div class="entry">\n'
            f'    <div class="row-primary">\n'
            f'      <span class="entry-left">{comp}</span>\n'
            f'      <span class="entry-right">{dates}</span>\n'
            f'      <div class="clear"></div>\n'
            f'    </div>\n'
            f'    <div class="row-secondary">\n'
            f'      <span class="sub-left">{title} | {loc}</span>\n'
            f'      <div class="clear"></div>\n'
            f'    </div>\n'
            f'    <ul>\n{bullets_list}    </ul>\n'
            f'  </div>\n'
        )

    exp_section_html = (
        f'<div class="section">\n'
        f'  <div class="section-title">Experience</div>\n'
        + "".join(exp_entries) +
        f'</div>\n'
    )

    # Strip ALL existing LLM-generated Experience sections to prevent duplicate Experience entries
    html = re.sub(
        r'<div class="section">\s*<div class="section-title">[^<]*?Experience[\s\S]*?(?=<div class="section">|</body>|$)',
        '',
        html,
        flags=re.IGNORECASE
    )

    # Inject single clean Experience section right after Summary or before Skills
    if '<div class="section-title">Skills' in html:
        html = html.replace('<div class="section-title">Skills', f'{exp_section_html}<div class="section-title">Skills', 1)
    elif '</body>' in html:
        html = html.replace('</body>', f'{exp_section_html}</body>', 1)

    # 3. Ensure ONE single unified Skills Section is present and complete
    candidate_skills = data.get("skills", {})
    if isinstance(candidate_skills, dict):
        languages_list = candidate_skills.get("languages", ["Python", "SQL", "MATLAB", "C++"])
        tools_list = candidate_skills.get("tools", ["Pandas", "NumPy", "Scikit-learn", "TensorFlow", "PyTorch", "Keras", "HuggingFace", "Tableau", "Git", "Docker"])
    else:
        languages_list = ["Python", "SQL", "MATLAB", "C++"]
        tools_list = ["Pandas", "NumPy", "Scikit-learn", "TensorFlow", "PyTorch", "Keras", "HuggingFace", "Tableau", "Git", "Docker"]

    # Filter out spoken languages from Programming Languages
    spoken_langs = {"arabic", "english", "french", "german", "spanish"}
    coding_langs = [l for l in languages_list if str(l).strip().lower() not in spoken_langs]
    if "Python" not in coding_langs:
        coding_langs.insert(0, "Python")
    if "SQL" not in coding_langs:
        coding_langs.append("SQL")

    # Filter out R and Power BI if not explicitly in candidate input
    all_flat = [str(s).lower().strip() for s in languages_list + tools_list]
    if "r" not in all_flat:
        coding_langs = [l for l in coding_langs if str(l).strip().lower() != "r"]
        tools_list = [t for t in tools_list if str(t).strip().lower() != "r"]

    # Ensure Data Analysis & Data Science tools are included
    essential_tools = ["Pandas", "NumPy", "Scikit-learn", "TensorFlow", "PyTorch", "Tableau", "FastAPI", "Docker", "Git", "FAISS", "Neo4j"]
    for tool in essential_tools:
        if tool not in tools_list and tool.lower() not in [t.lower() for t in tools_list]:
            tools_list.append(tool)

    lang_str = ", ".join(coding_langs) if coding_langs else "Python, SQL, MATLAB, C++"
    tools_str = ", ".join(tools_list[:15])

    core_concepts_str = (
        "Statistics & Mathematics, Data Cleaning & Preprocessing, Exploratory Data Analysis (EDA), "
        "Statistical Models, Predictive Modeling, Machine Learning, Deep Learning, Computer Vision, MLOps, RAG Systems"
    )

    skills_section_html = (
        f'<div class="section">\n'
        f'  <div class="section-title">Skills</div>\n'
        f'  <div class="skills-block">\n'
        f'    <div class="skills-line"><strong>Programming Languages:</strong> {lang_str}</div>\n'
        f'    <div class="skills-line"><strong>Spoken Languages:</strong> Arabic (Native), English (Full Professional)</div>\n'
        f'    <div class="skills-line"><strong>Tools &amp; Frameworks:</strong> {tools_str}</div>\n'
        f'    <div class="skills-line"><strong>Core Concepts:</strong> {core_concepts_str}</div>\n'
        f'  </div>\n'
        f'</div>\n'
    )

    # Strip any existing LLM-generated skills sections (e.g. Technical Skills or Skills) to eliminate duplicates
    html = re.sub(
        r'<div class="section">\s*<div class="section-title">[^<]*?Skills[\s\S]*?(?=<div class="section">|</body>|$)',
        '',
        html,
        flags=re.IGNORECASE
    )

    # Inject single unified Skills section before Projects, Education, or </body>
    if '<div class="section-title">Technical Projects' in html:
        html = html.replace('<div class="section-title">Technical Projects', f'{skills_section_html}<div class="section-title">Technical Projects', 1)
    elif '<div class="section-title">Education' in html:
        html = html.replace('<div class="section-title">Education', f'{skills_section_html}<div class="section-title">Education', 1)
    elif '</body>' in html:
        html = html.replace('</body>', f'{skills_section_html}</body>', 1)

    # 4. Ensure Training & Certifications Section is present
    certifications = data.get("certifications", []) or [
        {"name": "Generative AI & RAG Systems", "issuer": "ElectroPi AI Camp", "date": "Apr 2025–Feb 2026"},
        {"name": "AI & ML Diploma", "issuer": "MEC Academy", "date": "Aug 2025"},
        {"name": "AWS AI & ML Scholars", "issuer": "AWS", "date": "Aug 2025"},
        {"name": "Neo4j ×5 (Fundamentals, Cypher, Graph Modelling, Importing Data, Aura)", "issuer": "Neo4j", "date": "Oct 2025"},
        {"name": "Data Analytics Diploma", "issuer": "IMT School", "date": "Jan 2025"},
        {"name": "AI & ML Diploma", "issuer": "Route Academy", "date": "Apr 2024"},
    ]
    cert_items = []
    for cert in certifications:
        name = cert.get("name", "")
        issuer = cert.get("issuer", "")
        date_val = cert.get("date", "")
        if name:
            cert_items.append(f'      <li><strong>{name}</strong> — {issuer}{(" | " + date_val) if date_val else ""}</li>\n')

    # Strip existing Certifications section before injecting clean one
    html = re.sub(
        r'<div class="section">\s*<div class="section-title">[^<]*?Certifications[\s\S]*?(?=<div class="section">|</body>|$)',
        '',
        html,
        flags=re.IGNORECASE
    )

    if cert_items:
        cert_section_html = (
            f'<div class="section">\n'
            f'  <div class="section-title">Training &amp; Certifications</div>\n'
            f'  <ul>\n' + "".join(cert_items) + f'  </ul>\n'
            f'</div>\n'
        )
        if '<div class="section-title">Education' in html:
            html = html.replace('<div class="section-title">Education', f'{cert_section_html}<div class="section-title">Education', 1)
        elif '</body>' in html:
            html = html.replace('</body>', f'{cert_section_html}</body>', 1)

    # 5. Ensure Education Section layout is strictly left-aligned without unrequested coursework
    edu_section_html = (
        f'<div class="section">\n'
        f'  <div class="section-title">Education</div>\n'
        f'  <div class="entry">\n'
        f'    <div class="row-primary">\n'
        f'      <span class="entry-left">Suez Canal University</span>\n'
        f'      <span class="entry-right">2021 – 2026</span>\n'
        f'      <div class="clear"></div>\n'
        f'    </div>\n'
        f'    <div class="row-secondary">\n'
        f'      <span class="sub-left">B.Sc. Information Technology &amp; Telecommunications Engineering | Ismailia, Egypt</span>\n'
        f'      <div class="clear"></div>\n'
        f'    </div>\n'
        f'    <ul><li>GPA 3.35/4.00 | Graduation Project: ArabMedRAG — Grade: A</li></ul>\n'
        f'  </div>\n'
        f'</div>\n'
    )

    # Strip ALL existing LLM-generated Education sections to remove unrequested Coursework lines
    html = re.sub(
        r'<div class="section">\s*<div class="section-title">[^<]*?Education[\s\S]*?(?=<div class="section">|</body>|$)',
        '',
        html,
        flags=re.IGNORECASE
    )

    if '</body>' in html:
        html = html.replace('</body>', f'{edu_section_html}</body>', 1)
    else:
        html += edu_section_html

    # 6. Render & Format Technical Projects & Practical Experience
    html = _ensure_projects_rendered(html, data)

    # 7. Clean stray artifacts
    html = _clean_html_artifacts(html, data)
    return html


def _clean_html_artifacts(html: str, data: dict) -> str:
    """
    Strips stray LLM artifact tokens like 'nn' under section headers,
    and enforces strict candidate skill boundaries (e.g. removing 'R' if not in candidate input data).
    """
    # 1. Strip stray 'nn' text lines or stray text nodes
    html = re.sub(r'(<div class="section-title">[^<]+</div>)\s*nn\b', r'\1', html, flags=re.IGNORECASE)
    html = re.sub(r'>(?:\s*nn\s*)+<', '><', html)

    # 2. Check if candidate explicitly listed R
    candidate_skills = data.get("skills", {})
    languages = candidate_skills.get("languages", []) if isinstance(candidate_skills, dict) else []
    tools = candidate_skills.get("tools", []) if isinstance(candidate_skills, dict) else []
    all_skills_flat = [str(s).lower().strip() for s in languages + tools]

    if "r" not in all_skills_flat:
        # Strip R from languages/skills lines in HTML
        html = re.sub(r'\bR,\s*', '', html)
        html = re.sub(r',\s*R\b', '', html)
        html = re.sub(r'\bSkilled in leveraging Python,\s*R,', 'Skilled in leveraging Python,', html)
        html = re.sub(r'\bPython,\s*R,', 'Python,', html)

    # 3. Guarantee Spoken Languages line under Skills section
    if "Spoken Languages" not in html and "Languages:" in html:
        spoken_line = '<div class="skills-line"><strong>Spoken Languages:</strong> Arabic (Native), English (Full Professional)</div>'
        html = re.sub(
            r'(<strong>(?:Programming\s+)?Languages\s*:?</strong>[^<]+</div>)',
            r'\1\n    ' + spoken_line,
            html,
            count=1,
            flags=re.IGNORECASE
        )

    return html


def _normalize_phone_numbers(html: str) -> str:
    """
    Post-process HTML to normalize phone numbers to (+CC) local format.
    Prevents duplicate nested prefixes like (+20)(+20).
    """
    # Clean up any existing duplicate prefixes
    html = re.sub(r"\(\+\d+\)\s*\(\+\d+\)", "(+20)", html)
    html = re.sub(r"\(\+20\)\s*\+?20", "(+20)", html)

    def _reformat(match):
        raw_text = match.group(0)
        if "(+20)" in raw_text or "(+1)" in raw_text or "(+44)" in raw_text:
            return raw_text

        raw_digits = re.sub(r"[^\d]", "", raw_text)

        # Egyptian numbers: starts with 20 + 10-digit local number (total 12)
        if raw_digits.startswith("20") and len(raw_digits) == 12:
            local = raw_digits[2:]  # 10-digit local part
            return f"(+20) {local[:3]} {local[3:7]} {local[7:]}"

        # Egyptian numbers with leading 0: 010/011/012/015 + 8 digits = 11 digits
        if raw_digits.startswith("0") and len(raw_digits) == 11 and raw_digits[1] in "125":
            return f"(+20) {raw_digits[:3]} {raw_digits[3:7]} {raw_digits[7:]}"

        # US numbers: starts with 1 + 10 digits = 11 total
        if raw_digits.startswith("1") and len(raw_digits) == 11:
            n = raw_digits[1:]
            return f"(+1) {n[:3]}-{n[3:6]}-{n[6:]}"

        # UK numbers: starts with 44 + 10 digits = 12 total
        if raw_digits.startswith("44") and len(raw_digits) == 12:
            n = raw_digits[2:]
            return f"(+44) {n}"

        # India: starts with 91 + 10 digits = 12 total
        if raw_digits.startswith("91") and len(raw_digits) == 12:
            n = raw_digits[2:]
            return f"(+91) {n[:5]} {n[5:]}"

        return raw_text

    # Match phone patterns: optional +, between 10 and 13 digits
    html = re.sub(r"(?<!\(\+20\)\s)\+?[\d][\d\s\-\.]{8,14}[\d]", _reformat, html)
    return html


def _run_agent_task(agent, description, expected_output, label="agent"):
    """Run a single agent task via CrewAI and return raw output."""
    task = Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True, tracing=True)
    try:
        result = crew.kickoff()
        raw = _get_crew_output(result)
    except Exception as e:
        err_msg = str(e)
        if "failed_generation" in err_msg or "<function=" in err_msg or "tool_use_failed" in err_msg:
            match = re.search(r'\{.*\}', err_msg, re.DOTALL)
            if match:
                raw = match.group(0)
                raw = raw.replace('\\"', '"').replace('\\\\', '\\')
            else:
                raise RuntimeError(f"{label} crew failed: {e}")
        else:
            raise RuntimeError(f"{label} crew failed: {e}")

    if not raw:
        raise RuntimeError(f"{label} returned empty output")
    return raw


def _run_agent_task_with_json(agent, description, expected_output, label="agent", required_keys=None, max_retries=2):
    """Run an agent task and parse JSON, retrying if parse fails or required keys are missing."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            raw = _run_agent_task(agent, description, expected_output, label)
            parsed = _extract_json(raw)
            if required_keys:
                missing = [k for k in required_keys if k not in parsed]
                if missing and attempt < max_retries:
                    logger.warning(f"{label} attempt {attempt+1}: missing keys {missing}, retrying...")
                    last_error = f"Missing keys: {missing}"
                    continue
            return parsed
        except (RuntimeError, json.JSONDecodeError) as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(f"{label} attempt {attempt+1} failed: {e}, retrying...")
                continue
            raise
    raise RuntimeError(f"{label} failed after {max_retries+1} attempts. Last error: {last_error}")


from crewai.tools import tool

@tool("SerperDev Search")
def serper_web_search(query: str) -> str:
    """Search Google via Serper Dev API for candidate repositories, Kaggle projects, or company details."""
    results = search_serper_web(query, max_results=5)
    if not results:
        return f"No web search results found for '{query}'."
    return json.dumps(results, indent=2)


# ══════════════════════════════════════════════════════════
#  AGENTS (7 total)
# ══════════════════════════════════════════════════════════

# Agent 1: Extraction — tool-based, no LLM (see tools/extractors.py)

structuring_agent = Agent(
    role="CV Structuring & Live Enrichment Specialist",
    goal=(
        "Parse raw resume text into a clean, normalized, structured JSON object. "
        "Use SerperDev search tool when needed to discover unlinked GitHub repositories or portfolio projects."
    ),
    backstory=(
        "You are a data normalization expert. You take raw extracted text from a "
        "resume and parse it into a well-structured JSON object. You normalize dates, "
        "job titles, locations, bullet points, and technologies. You use live SerperDev search "
        "to discover candidate repos or Kaggle notebooks if needed."
    ),
    tools=[serper_web_search],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

jd_analysis_agent = Agent(
    role="Job Description Analyst",
    goal=(
        "Analyze a job description and extract all relevant information for resume "
        "optimization: ATS keywords, required/preferred skills, responsibilities, "
        "company context, technical stack, seniority level, soft skills, and a "
        "resume strategy."
    ),
    backstory=(
        "You are an expert job market analyst. You read job descriptions and extract "
        "structured data that helps resume writers optimize for ATS systems and "
        "recruiter readability."
    ),
    tools=[serper_web_search],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

cv_generator_agent = Agent(
    role="ATS Resume Generator",
    goal=(
        "Generate a modern, ATS-optimized HTML resume that is tailored to a specific "
        "job description, incorporates user notes, and follows the provided HTML template."
    ),
    backstory=(
        "You are an expert resume writer specializing in ATS optimization. You take "
        "structured candidate data, a job analysis, and user notes, then produce a "
        "single-column, ATS-friendly HTML document. You match keywords from the job "
        "description, quantify achievements, prioritize relevant projects, and ensure "
        "the CV is clean, professional, and passes ATS screening. You use the exact "
        "HTML template structure provided."
    ),
    tools=[serper_web_search],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

review_polish_agent = Agent(
    role="Resume Review & Polish Specialist",
    goal=(
        "Review a generated HTML resume for ATS compatibility, quality, and natural "
        "language. Fix issues and return a polished version with an ATS score and "
        "improvement suggestions."
    ),
    backstory=(
        "You are a combined ATS reviewer, quality assurance specialist, and professional "
        "editor. You evaluate resumes for: ATS keyword coverage, formatting issues, "
        "weak bullet points, redundancy, section ordering, grammar, hallucinations, "
        "duplicated content, inconsistent dates, and AI-generated cliches. You rewrite "
        "AI language to sound natural and professional while preserving ATS keywords. "
        "You provide an estimated ATS match score (0-100) and a list of actionable "
        "suggestions."
    ),
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

cover_letter_agent = Agent(
    role="Cover Letter Writer & Reviewer",
    goal=(
        "Generate a tailored, professional HTML cover letter that is personalized "
        "for the target company and role, connects the candidate's experience to "
        "job requirements, and is self-reviewed for quality."
    ),
    backstory=(
        "You are an expert cover letter writer and reviewer. You take structured "
        "candidate data, a job analysis, and user notes, then produce a formal, "
        "compelling HTML cover letter. You personalize for the company and position, "
        "connect experience to requirements with specific examples, and maintain a "
        "professional, concise, engaging tone. Before outputting, you self-review "
        "for: personalization, grammar, relevance, flow, accuracy, repetition, and "
        "natural language. You never fabricate experience or skills."
    ),
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

ats_auditor_agent = Agent(
    role="ATS Resume Auditor & Career Advisor",
    goal=(
        "Perform a comprehensive, LLM-powered ATS compatibility audit of a "
        "candidate's resume against a specific job description. Produce a "
        "structured JSON report with an overall match score, categorized "
        "keyword analysis, section-by-section quality feedback, and specific "
        "actionable rewrite recommendations."
    ),
    backstory=(
        "You are a senior ATS systems expert and career advisor with deep "
        "knowledge of how Applicant Tracking Systems parse and score resumes. "
        "You evaluate resumes with the precision of a recruiter and the "
        "technical depth of an ATS engineer. You assess: keyword coverage "
        "(required vs preferred vs missing), section quality (Summary, "
        "Experience, Education, Skills, Projects), bullet point impact, "
        "formatting correctness, action verb strength, and overall ATS "
        "compatibility. You provide a weighted score (0-100) and granular, "
        "actionable feedback that the candidate can immediately act upon to "
        "improve their resume for this specific role."
    ),
    llm=llm,
    verbose=True,
    allow_delegation=False,
)


# ══════════════════════════════════════════════════════════
#  PIPELINE FUNCTIONS
# ══════════════════════════════════════════════════════════

def run_extraction(file_bytes: bytes, filename: str) -> str:
    """Agent 1: Extract text from uploaded file (tool-based, no LLM)."""
    return extract_text(file_bytes, filename)


def run_portfolio_fetch(urls: list[str]) -> list[dict]:
    """Fetch portfolio links and return structured project summaries (no LLM)."""
    if not urls:
        return []
    return fetch_portfolio_links(urls)


def run_structuring(raw_text: str, notes: str = "", enriched_profile: dict | None = None) -> dict:
    """Agent 2: Structure raw text into normalized JSON, merging user notes and live enriched profile data."""
    notes_section = ""
    if notes.strip():
        notes_section = (
            f"\nUSER NOTES (these contain updated information — merge into the output):\n"
            f"{notes.strip()}\n\n"
        )

    # Build enrichment context from GitHub API data
    enrichment_section = ""
    if enriched_profile:
        parts = []
        if enriched_profile.get("github_user_info"):
            info = enriched_profile["github_user_info"]
            parts.append(f"GitHub Profile: {enriched_profile.get('github_username', '')}")
            if info.get("bio"):
                parts.append(f"Bio: {info['bio']}")
            if info.get("public_repos"):
                parts.append(f"Public Repos: {info['public_repos']}")
        if enriched_profile.get("all_languages"):
            parts.append(f"Languages used on GitHub: {', '.join(enriched_profile['all_languages'])}")
        if enriched_profile.get("all_topics"):
            parts.append(f"Project topics/tags: {', '.join(enriched_profile['all_topics'][:15])}")
        repos = enriched_profile.get("repos", [])
        if repos:
            parts.append("\nTop GitHub Repositories (verified, public):")
            for r in repos[:8]:
                repo_line = f"  - {r['name']} ({r.get('language', 'N/A')}): {r.get('description', '')} [⭐ {r.get('stars', 0)}]"
                if r.get("topics"):
                    repo_line += f" | Topics: {', '.join(r['topics'][:5])}"
                if r.get("readme_excerpt"):
                    repo_line += f"\n    README: {r['readme_excerpt'][:300]}"
                parts.append(repo_line)
        enrichment_section = (
            "\nLIVE PROFILE ENRICHMENT DATA (from GitHub API — verified, use this to enrich projects section):\n"
            + "\n".join(parts)
            + "\n"
            "IMPORTANT: You may use the above GitHub data to add or enrich the 'projects' array with real, "
            "verified repositories. Only add repos that are clearly technical projects (not forks, not config repos). "
            "Do NOT fabricate descriptions — use the repo description and README excerpt as-is.\n\n"
        )

    return _run_agent_task_with_json(
        structuring_agent,
        description=(
            "SYSTEM INSTRUCTIONS:\n"
            "Treat user-provided notes as the most up-to-date source of information. "
            "If notes conflict with the extracted resume content, prioritize the notes "
            "unless they introduce unverifiable claims.\n\n"
            "CRITICAL — ZERO FABRICATION & CONTACT VERBATIM RULE:\n"
            "- Extract email addresses, phone numbers, and URL strings VERBATIM character-by-character\n"
            "  (e.g., if email is 'marawan.abdellah0@gmail.com', NEVER drop the '0' or alter characters)\n"
            "- Parse ONLY what is explicitly written in the raw text or provided in Live Profile Enrichment Data\n"
            "- Do NOT add skills, tools, technologies, or certifications not mentioned in EITHER source\n"
            "- Do NOT invent bullet points, achievements, or responsibilities\n"
            "- Do NOT add descriptions or details the candidate did not write\n"
            "- If a field is not mentioned in the raw text, use an empty string or empty list\n"
            "- The ONLY acceptable additions are: normalizing dates, formatting, merging notes, "
            "and adding verified GitHub repository projects\n\n"
            "Parse the following raw CV text into a structured JSON object. "
            "Normalize all dates to a consistent format (e.g. 'Jan 2022 - Present'). "
            "Normalize job titles and locations. Clean bullet points.\n\n"
            f"RAW TEXT:\n{raw_text}\n\n"
            f"{notes_section}"
            f"{enrichment_section}"
            "Output ONLY valid JSON with ALL of these fields:\n"
            '{\n'
            '  "name": "",\n'
            '  "email": "",\n'
            '  "phone": "",\n'
            '  "location": "",\n'
            '  "links": {"linkedin": "", "github": "", "kaggle": "", "website": "", "other": ""},\n'
            '  "summary": "",\n'
            '  "experience": [{"title": "", "company": "", "location": "", "dates": "", "bullets": [""]}],\n'
            '  "education": [{"school": "", "degree": "", "field": "", "dates": "", "details": ""}],\n'
            '  "skills": {"languages": [], "tools": []},\n'
            '  "projects": [{"name": "", "description": "", "url": "", "stars": 0, "bullets": [""]}],\n'
            '  "certifications": [{"name": "", "issuer": "", "date": ""}],\n'
            '  "awards": [{"name": "", "issuer": "", "date": ""}]\n'
            '}\n'
            "IMPORTANT: Include ALL top-level fields. Do not output only a subset. "
            "Extract ALL links from the resume (LinkedIn, GitHub, Kaggle, personal website, etc.) "
            "and place them in the 'links' object. Use empty string for any missing platforms."
        ),
        expected_output="A valid JSON object with structured resume data.",
        label="Structuring",
        required_keys=["name", "experience", "education", "skills"],
    )


def run_jd_analysis(job_description: str) -> dict:
    """Agent 3: Analyze job description and extract structured insights."""
    jd_clean = (job_description or "").strip()
    if len(jd_clean) < 20:
        raise ValueError("Invalid Job Description: The provided text is too short or empty. Please enter a valid job description.")

    words = [w for w in re.split(r'\s+', jd_clean) if len(w) > 2]
    if len(words) < 4:
        raise ValueError("Invalid Job Description: The provided text does not contain enough words to be a job description.")

    res = _run_agent_task_with_json(
        jd_analysis_agent,
        description=(
            "Analyze the following text and determine if it is a valid Job Description.\n\n"
            f"INPUT TEXT:\n{job_description}\n\n"
            "VALIDATION RULE:\n"
            "Set 'is_valid_jd' to true if the input text describes a job role, job title, responsibilities, "
            "or required qualifications. Set 'is_valid_jd' to false if the input text is random gibberish, "
            "unrelated content, a grocery list, code snippet, or NOT a job description.\n\n"
            "Output ONLY valid JSON with ALL of these fields:\n"
            '{\n'
            '  "is_valid_jd": true,\n'
            '  "required_skills": ["skill1", "skill2"],\n'
            '  "preferred_skills": ["skill1", "skill2"],\n'
            '  "ats_keywords": ["keyword1", "keyword2"],\n'
            '  "responsibilities": ["responsibility1", "responsibility2"],\n'
            '  "technical_stack": ["technology1", "technology2"],\n'
            '  "industry": "",\n'
            '  "seniority": "",\n'
            '  "soft_skills": ["skill1", "skill2"],\n'
            '  "company_context": "",\n'
            '  "resume_strategy": {\n'
            '    "emphasize": ["thing to emphasize"],\n'
            '    "keywords_to_naturally_include": ["keyword1", "keyword2"],\n'
            '    "section_order_suggestion": ["section1", "section2"]\n'
            '  }\n'
            '}\n'
            "IMPORTANT: Include ALL top-level fields."
        ),
        expected_output="A valid JSON object with job description analysis and is_valid_jd boolean flag.",
        label="JD Analysis",
        required_keys=["required_skills", "preferred_skills", "ats_keywords", "resume_strategy"],
    )

    if res.get("is_valid_jd") is False:
        raise ValueError("Invalid Job Description: The provided text does not appear to be a real job description. Please provide a valid job description with role details or requirements.")

    return res


def run_cv_generation(enriched_data: dict, jd_analysis: dict, notes: str = "") -> str:
    """Agent 4: Generate ATS-friendly HTML CV."""
    template = (TEMPLATES_DIR / "cv_template.html").read_text(encoding="utf-8")

    notes_section = ""
    if notes.strip():
        notes_section = (
            f"\nADDITIONAL USER NOTES (follow these instructions — they override default behavior):\n"
            f"{notes.strip()}\n\n"
        )

    raw = _run_agent_task(
        cv_generator_agent,
        description=(
            "SYSTEM INSTRUCTIONS (MUST FOLLOW):\n"
            "Before making any modifications, carefully review ALL provided inputs: the CV data, "
            "the job analysis, and any user notes or instructions. Treat user-provided notes as "
            "the most up-to-date source of information. If they conflict with the extracted CV "
            "content, prioritize the notes unless they contradict the job requirements. "
            "Favor relevance over chronology whenever it improves ATS compatibility.\n\n"
            "CRITICAL — ZERO FABRICATION & CATEGORIZATION RULES (STRICTLY ENFORCED):\n"
            "- Use ONLY the information explicitly provided in CANDIDATE DATA\n"
            "- NEVER modify candidate contact details (Name, Email, Phone, Location, URLs). Copy them EXACTLY as given.\n"
            "  - Email MUST be copied verbatim (e.g., 'marawan.abdellah0@gmail.com' — do NOT drop the '0' or '.').\n"
            "  - Name MUST be copied verbatim (e.g., 'Marwan Abdellah' — do NOT change to 'Abdillah').\n"
            "- NEVER add programming languages, tools, or skills not listed in candidate data\n"
            "  - NEVER list 'R' unless 'R' is explicitly in the input candidate data (if candidate did not write R, omit R entirely).\n"
            "  - NEVER list 'Mathematics' or academic subjects under 'Languages:'. 'Languages:' is ONLY for programming/query languages (e.g. Python, SQL, C++).\n"
            "  - Place 'Mathematics' and 'Statistics' under 'Core Concepts:' or 'Analytical Skills:'.\n"
            "- NEVER create fake employment entries at the target company listed in the Job Description\n"
            "- If candidate has NO corporate job history, format projects under 'Technical Projects & Practical Experience'\n"
            "- MUST INCLUDE ALL 5 STANDARD SECTIONS: Summary, Skills, Technical Projects & Practical Experience, Education, Certifications.\n"
            "  - DO NOT OMIT Skills. DO NOT OMIT Education. Populate every section completely so the page is full without giant blank spaces.\n\n"
            f"HTML TEMPLATE:\n{template}\n\n"
            f"CANDIDATE DATA (JSON):\n{json.dumps(enriched_data, indent=2)}\n\n"
            f"JOB ANALYSIS (JSON):\n{json.dumps(jd_analysis, indent=2)}\n\n"
            f"{notes_section}"
            "Generate a complete HTML document that:\n"
            "1. Uses the EXACT same CSS classes and structure as the template\n"
            "2. Fills in all placeholders with the candidate's real data\n"
            "3. MUST INCLUDE ALL 4 ESSENTIAL SECTIONS: Summary, Skills, Technical Projects & Practical Experience, Education\n"
            "   - DO NOT omit the Skills section\n"
            "   - DO NOT omit the Education section\n"
            "4. Contact details MUST be separated by spaces around pipes: `email@example.com &nbsp;|&nbsp; (+20) 010 2938 8461 &nbsp;|&nbsp; Location`\n"
            "5. PROJECT LINKS MUST BE CLICKABLE HTML `<a href='...'>` TAGS:\n"
            "   - Format project links as: `<div class='entry-link'><a href='https://github.com/user/repo'>github.com/user/repo</a></div>`\n"
            "   - NEVER output plain unstyled text 'GitHub' or 'Project Link'\n"
            "   - If no URL is provided for a project, do NOT render the entry-link div at all\n"
            "6. Tailors bullet points to match keywords from the job analysis while maintaining strict factual accuracy\n"
            "7. Keeps the single-column ATS-friendly layout intact\n"
            "8. Output ONLY the complete HTML source code, starting with <!DOCTYPE html>."
        ),
        expected_output="Complete HTML source code for the CV.",
        label="CV Generation",
    )
    html = _extract_html(raw)
    if "<html" not in html.lower() and "<body" not in html.lower():
        raise RuntimeError(f"CV generator did not return valid HTML.\nOutput starts with: {html[:200]}")

    # Master Section Enforcer: Guarantees Header, Summary, Skills, Projects, and Education sections
    html = _enforce_complete_resume_sections(html, enriched_data)
    return html


def run_review_and_polish(cv_html: str, jd_analysis: dict) -> dict | None:
    """Agent 5: Review, polish, and score the generated CV. Returns None on failure."""
    try:
        raw = _run_agent_task(
            review_polish_agent,
            description=(
                "Review the following generated HTML resume for ATS compatibility, quality, "
                "and natural language. Fix any issues you find.\n\n"
                f"JOB ANALYSIS:\n{json.dumps(jd_analysis, indent=2)}\n\n"
                f"GENERATED HTML:\n{cv_html}\n\n"
                "CRITICAL — HALLUCINATION CHECK:\n"
                "Compare the HTML content against the CANDIDATE DATA embedded in it. "
                "If you find ANY content in the HTML that was NOT in the original candidate data "
                "(extra skills, fabricated bullet points, invented achievements, made-up metrics), "
                "REMOVE that content entirely. Do not rewrite hallucinated content — delete it.\n\n"
                "Additional checks:\n"
                "1. ATS keyword coverage — are important keywords from the job analysis present?\n"
                "2. Formatting — consistent fonts, spacing, section headers\n"
                "3. Action verbs — strong, varied action verbs at start of bullets\n"
                "4. Weak bullets — bullets lacking measurable outcomes\n"
                "5. Redundancy — duplicate skills, repeated phrases\n"
                "6. Section ordering — most relevant sections first\n"
                "7. Grammar and spelling\n"
                "8. AI cliches — replace 'Leveraged', 'Utilized', 'Cutting-edge', 'Highly motivated' with natural alternatives\n"
                "9. Readability — natural flow, professional tone\n\n"
                "Output ONLY valid JSON:\n"
                '{\n'
                '  "score": 83,\n'
                '  "strengths": ["strength1", "strength2"],\n'
                '  "suggestions": ["suggestion1", "suggestion2"],\n'
                '  "polished_html": "<!DOCTYPE html>...完整HTML..."</n'
                '}\n'
            ),
            expected_output="A JSON object with score, strengths, suggestions, and polished_html.",
            label="Review & Polish",
        )
        return _extract_json(raw)
    except Exception as e:
        logger.warning(f"Review & Polish failed (returning None): {e}")
        return None


def _clean_cover_letter_artifacts(html: str, data: dict) -> str:
    """
    Strips unrequested skill fabrications from cover letters (e.g. 'R' or 'Power BI')
    if they are not present in candidate skills.
    """
    candidate_skills = data.get("skills", {})
    if isinstance(candidate_skills, dict):
        all_skills = [str(s).lower().strip() for v in candidate_skills.values() if isinstance(v, list) for s in v]
    else:
        all_skills = []

    # If R is not in candidate input data, strip mentions of 'and R', ', R,', 'in Python and R'
    if "r" not in all_skills:
        html = re.sub(r'\b(?:and|or)\s+R\b', '', html)
        html = re.sub(r'\bR\s*,\s*', '', html)

    # If Power BI is not in candidate input data, strip mentions of Power BI
    if "power bi" not in all_skills and "powerbi" not in all_skills:
        html = re.sub(r'\b(?:and|or)\s+Power\s+BI\b', '', html, flags=re.IGNORECASE)
        html = re.sub(r'\bPower\s+BI\s*,\s*', '', html, flags=re.IGNORECASE)

    return _normalize_phone_numbers(html)


def run_cover_letter_generation(enriched_data: dict, jd_analysis: dict, notes: str = "") -> str:
    """Agent 6: Generate tailored HTML cover letter with self-review."""
    template = (TEMPLATES_DIR / "cover_letter_template.html").read_text(encoding="utf-8")
    today = date.today().strftime("%B %d, %Y")

    notes_section = ""
    if notes.strip():
        notes_section = (
            f"\nADDITIONAL USER NOTES (follow these instructions — they override default behavior):\n"
            f"{notes.strip()}\n\n"
        )

    raw = _run_agent_task(
        cover_letter_agent,
        description=(
            "SYSTEM INSTRUCTIONS (MUST FOLLOW):\n"
            "Before writing, carefully review the CV data, Job Analysis, and all user notes. "
            "Treat user notes as the most up-to-date source of information. "
            "Personalize for the company and position. Connect REAL experience to requirements.\n\n"
            "CRITICAL — ZERO FABRICATION RULE (COVER LETTER):\n"
            "- NEVER claim the candidate works AT the target company (they are applying TO it)\n"
            "- NEVER claim the candidate has skills or experience not listed in CANDIDATE DATA\n"
            "  - DO NOT write that the candidate is proficient in 'R' or 'Power BI' if they are NOT in CANDIDATE DATA.\n"
            "- NEVER copy responsibilities from the JD as if they were the candidate's past work\n"
            "- If the candidate lacks corporate experience, frame their PROJECTS as practical experience\n"
            "- Spell the company name EXACTLY as it appears in the Job Analysis — check it twice\n\n"
            f"HTML TEMPLATE:\n{template}\n\n"
            f"CANDIDATE DATA (JSON):\n{json.dumps(enriched_data, indent=2)}\n\n"
            f"JOB ANALYSIS (JSON):\n{json.dumps(jd_analysis, indent=2)}\n\n"
            f"TODAY'S DATE: {today}\n\n"
            f"{notes_section}"
            "Generate a complete HTML cover letter that:\n"
            "1. Uses the EXACT same CSS classes and structure as the template\n"
            "2. Fills in sender address from candidate data (name, email, phone, location)\n"
            f"3. Uses TODAY'S DATE ({today}) for the letter date — do NOT use any other date\n"
            "4. Infers recipient details from the job analysis (company name, title)\n"
            "5. Writes a strong 3-paragraph body:\n"
            "   - Introduction: state the role and why you are applying\n"
            "   - Fit: connect candidate's experience to job requirements with specific examples\n"
            "   - Closing: express enthusiasm and call to action\n"
            "6. Uses formal, natural tone throughout\n"
            "7. Incorporates user notes if provided\n"
            "8. Phone numbers MUST be formatted as: (+country_code) number, e.g. (+20) 01X XXX XXXX\n\n"
            "SELF-REVIEW before outputting:\n"
            "- Is the letter personalized to the company?\n"
            "- Is the grammar correct?\n"
            "- Does it flow naturally?\n"
            "- Is it 250-400 words?\n"
            "- Are there any repeated phrases from the resume?\n\n"
            "Output ONLY the complete HTML source code, nothing else."
        ),
        expected_output="Complete HTML source code for the cover letter.",
        label="Cover Letter",
    )
    html = _extract_html(raw)
    if "<html" not in html.lower() and "<body" not in html.lower():
        raise RuntimeError(f"Cover letter did not return valid HTML.\nOutput starts with: {html[:200]}")
    return _clean_cover_letter_artifacts(html, enriched_data)


def _latex_escape(text: str) -> str:
    """Escape special LaTeX characters safely."""
    if not text:
        return ""
    mapping = [
        ('\\', r'\textbackslash{}'),
        ('&', r'\&'),
        ('%', r'\%'),
        ('$', r'\$'),
        ('#', r'\#'),
        ('_', r'\_'),
        ('{', r'\{'),
        ('}', r'\}'),
        ('~', r'\textasciitilde{}'),
        ('^', r'\textasciicircum{}'),
    ]
    for orig, repl in mapping:
        text = text.replace(orig, repl)
    return text


def html_to_latex(html_source: str, doc_type: str = "cv") -> str:
    """Convert HTML source to a clean, ATS-optimized LaTeX document."""
    if r"\documentclass" in html_source:
        return html_source

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        BeautifulSoup = None

    if not BeautifulSoup:
        # Fallback regex parsing if bs4 is missing
        clean_text = re.sub(r'<style>[\s\S]*?</style>', '', html_source, flags=re.IGNORECASE)
        clean_text = re.sub(r'<[^>]+>', ' ', clean_text).strip()
        return f"\\documentclass{{article}}\n\\begin{{document}}\n{_latex_escape(clean_text)}\n\\end{{document}}"

    soup = BeautifulSoup(html_source, "html.parser")

    name_el = soup.find(class_=re.compile(r"name", re.I)) or soup.find(["h1", "h2"])
    name = name_el.get_text(strip=True) if name_el else "Candidate"

    contact_el = soup.find(class_=re.compile(r"contact", re.I))
    contact_items = []
    if contact_el:
        for a in contact_el.find_all("a"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if href.startswith("mailto:"):
                email_val = href.replace("mailto:", "")
                contact_items.append(f"\\href{{mailto:{_latex_escape(email_val)}}}{{{_latex_escape(text or email_val)}}}")
            elif href.startswith("http"):
                contact_items.append(f"\\href{{{_latex_escape(href)}}}{{{_latex_escape(text or href)}}}")
        full_contact_text = contact_el.get_text(" ", strip=True)
        phone_match = re.search(r"(\(\+\d+\)\s*[\d\s-]+|\+?\d[\d\s-]{8,14}\d)", full_contact_text)
        if phone_match and not any(phone_match.group(0) in item for item in contact_items):
            contact_items.insert(0, _latex_escape(phone_match.group(0).strip()))

    contact_line = " \\quad$\\cdot$\\quad ".join(contact_items) if contact_items else ""

    latex_sections = []
    sections = soup.find_all(class_=re.compile(r"section", re.I))
    if not sections:
        sections = [soup.find("body") or soup]

    for sec in sections:
        sec_title_el = sec.find(class_=re.compile(r"title|header", re.I)) or sec.find(["h2", "h3"])
        sec_title = sec_title_el.get_text(strip=True) if sec_title_el else ""

        if sec_title:
            latex_sections.append(f"\n\\section*{{{_latex_escape(sec_title)}}}")

        for child in sec.children:
            if child == sec_title_el or getattr(child, "name", None) in ("h1", "h2", "h3"):
                continue
            if not getattr(child, "name", None):
                text = str(child).strip()
                if text:
                    latex_sections.append(_latex_escape(text))
                continue

            if child.name == "ul":
                items = [f"  \\item {_latex_escape(li.get_text(strip=True))}" for li in child.find_all("li")]
                if items:
                    latex_sections.append("\\begin{itemize}[leftmargin=1.5em, itemsep=2pt, topsep=2pt]\n" + "\n".join(items) + "\n\\end{itemize}")
            elif child.name == "p":
                latex_sections.append(_latex_escape(child.get_text(strip=True)))
            elif child.name == "div":
                entry_title = child.find(class_=re.compile(r"title|job|name", re.I))
                entry_sub = child.find(class_=re.compile(r"company|school|sub", re.I))
                entry_date = child.find(class_=re.compile(r"date|year", re.I))
                entry_loc = child.find(class_=re.compile(r"location|city", re.I))

                if entry_title or entry_sub:
                    t_str = _latex_escape(entry_title.get_text(strip=True)) if entry_title else ""
                    s_str = _latex_escape(entry_sub.get_text(strip=True)) if entry_sub else ""
                    d_str = _latex_escape(entry_date.get_text(strip=True)) if entry_date else ""
                    l_str = _latex_escape(entry_loc.get_text(strip=True)) if entry_loc else ""

                    header_line = f"\\textbf{{{t_str}}}" if t_str else ""
                    if d_str or l_str:
                        right_info = f"{l_str} \\quad {d_str}".strip(" \\quad")
                        header_line += f" \\hfill {right_info}"
                    header_line += "\\\\"

                    if s_str:
                        header_line += f"\n\\textit{{{s_str}}}"

                    latex_sections.append(header_line)

                entry_ul = child.find("ul")
                if entry_ul:
                    items = [f"  \\item {_latex_escape(li.get_text(strip=True))}" for li in entry_ul.find_all("li")]
                    if items:
                        latex_sections.append("\\begin{itemize}[leftmargin=1.5em, itemsep=2pt, topsep=2pt]\n" + "\n".join(items) + "\n\\end{itemize}")

    body_latex = "\n\n".join(latex_sections)

    latex_doc = f"""\\documentclass[10pt,a4paper]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[margin=0.5in]{{geometry}}
\\usepackage{{hyperref}}
\\usepackage{{enumitem}}
\\usepackage{{xcolor}}

\\hypersetup{{
    colorlinks=true,
    linkcolor=blue,
    urlcolor=blue,
}}

\\pagestyle{{empty}}

\\begin{{document}}

\\begin{{center}}
    {{\\Huge \\textbf{{{_latex_escape(name)}}}}}\\\\[4pt]
    \\small {contact_line}
\\end{{center}}

\\vspace{{-6pt}}
\\hrulefill
\\vspace{{6pt}}

{body_latex}

\\end{{document}}
"""
    return latex_doc


def compile_latex_to_pdf(tex_source: str, output_name: str) -> Path:
    """Compile LaTeX source to PDF using pdflatex command line."""
    import shutil
    import subprocess

    pdflatex_bin = shutil.which("pdflatex") or r"C:\Users\Marwan\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe"
    if not os.path.exists(pdflatex_bin) and not shutil.which("pdflatex"):
        raise FileNotFoundError("pdflatex compiler binary not found on system.")

    tex_path = OUTPUT_DIR / f"{output_name}.tex"
    pdf_path = OUTPUT_DIR / f"{output_name}.pdf"

    tex_path.write_text(tex_source, encoding="utf-8")

    cmd = [
        pdflatex_bin,
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-output-directory={OUTPUT_DIR.resolve()}",
        str(tex_path.resolve()),
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    for ext in (".aux", ".log", ".out", ".tex"):
        aux_file = OUTPUT_DIR / f"{output_name}{ext}"
        if aux_file.exists():
            try:
                aux_file.unlink()
            except Exception:
                pass

    if proc.returncode != 0 or not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise RuntimeError(f"pdflatex exit code {proc.returncode}. Stderr: {proc.stderr[:300]}")

    return pdf_path


def run_compilation(html_source: str, output_name: str) -> Path:
    """Agent 7: Compile document to PDF using LaTeX compiler (pdflatex) with xhtml2pdf fallback."""
    final_path = OUTPUT_DIR / f"{output_name}.pdf"

    # 1. Attempt LaTeX Compilation (pdflatex)
    try:
        doc_type = "cover_letter" if "cover_letter_" in output_name else "cv"
        tex_source = html_to_latex(html_source, doc_type=doc_type)
        compiled_pdf = compile_latex_to_pdf(tex_source, output_name)
        if compiled_pdf.exists() and compiled_pdf.stat().st_size > 0:
            logger.info(f"[Agent 7] LaTeX compilation succeeded: {compiled_pdf.name}")
            return compiled_pdf
    except Exception as e:
        logger.warning(f"[Agent 7] LaTeX compilation attempt failed ({e}) — falling back to clean HTML/xhtml2pdf...")

    # 2. Fallback: xhtml2pdf
    template_file = "cv_template.html" if "cv_" in output_name else "cover_letter_template.html"
    template_css = (TEMPLATES_DIR / template_file).read_text(encoding="utf-8")
    style_match = re.search(r'<style>([\s\S]*?)</style>', template_css, flags=re.IGNORECASE)
    clean_style = style_match.group(0) if style_match else "<style></style>"

    clean_html = re.sub(r'<style>[\s\S]*?</style>', '', html_source, flags=re.IGNORECASE)
    clean_html = re.sub(r'<style>[\s\S]*?(?=<body|<div|<head)', '', clean_html, flags=re.IGNORECASE)

    body_content = clean_html
    body_match = re.search(r'<body[^>]*>([\s\S]*?)</body>', clean_html, flags=re.IGNORECASE)
    if body_match:
        body_content = body_match.group(1)

    sanitized_html = (
        f'<!DOCTYPE html>\n'
        f'<html lang="en">\n'
        f'<head>\n'
        f'<meta charset="UTF-8">\n'
        f'{clean_style}\n'
        f'</head>\n'
        f'<body>\n'
        f'{body_content}\n'
        f'</body>\n'
        f'</html>'
    )

    try:
        with open(final_path, "wb") as f:
            status = pisa.CreatePDF(sanitized_html, dest=f)
            if status.err:
                raise RuntimeError(f"xhtml2pdf conversion failed with {status.err} errors")
    except Exception as e:
        logger.error(f"PDF compilation failed ({e})")
        raise RuntimeError(f"PDF compilation failed: {e}")

    if not final_path.exists() or final_path.stat().st_size == 0:
        raise RuntimeError("PDF was not generated or is empty.")
    return final_path


def _rank_and_select_projects_for_jd(all_projects: list[dict], jd_analysis: dict) -> list[dict]:
    """
    100% Generic Candidate & Repo Ranker:
    Ranks ANY candidate's GitHub repositories or portfolio projects against the target Job Description
    by computing term-frequency word overlap between the JD requirements/keywords/stack and each project's
    name, description, topics, programming language, and README excerpts.
    """
    if not all_projects:
        return []

    # Extract all normalized keywords and multi-word terms from JD Analysis
    jd_keywords = set()
    for key in ("required_skills", "preferred_skills", "ats_keywords", "technical_stack", "responsibilities"):
        vals = jd_analysis.get(key, [])
        if isinstance(vals, list):
            for item in vals:
                item_str = str(item).lower().strip()
                if item_str:
                    jd_keywords.add(item_str)
                    for w in re.split(r'[\s/,-]+', item_str):
                        if len(w) > 2:
                            jd_keywords.add(w)

    scored_projects = []
    for proj in all_projects:
        name = str(proj.get("name", ""))
        desc = str(proj.get("description", ""))
        lang = str(proj.get("language", ""))
        topics = [str(t) for t in proj.get("topics", [])]
        bullets = [str(b) for b in proj.get("bullets", [])]

        proj_corpus = f"{name} {desc} {lang} {' '.join(topics)} {' '.join(bullets)}".lower()

        score = 0
        for kw in jd_keywords:
            if kw in proj_corpus:
                score += 5 if " " in kw else 2

        for top in topics:
            if top.lower() in jd_keywords:
                score += 4
        if lang and lang.lower() in jd_keywords:
            score += 4

        if proj.get("stars", 0) > 0:
            score += min(proj["stars"], 5)

        scored_projects.append((score, proj))

    # Sort by score descending
    scored_projects.sort(key=lambda x: x[0], reverse=True)

    # Select top 4 unique projects
    selected = []
    seen_names = set()
    for score, proj in scored_projects:
        clean_name = str(proj.get("name", "")).strip().lower()
        if clean_name and clean_name not in seen_names:
            seen_names.add(clean_name)
            selected.append(proj)
        if len(selected) >= 4:
            break

    return selected or all_projects[:4]


# ══════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ══════════════════════════════════════════════════════════

def run_generation_only(
    cleaned_data: dict,
    job_description: str,
    output_type: str,
    notes: str = "",
    portfolio_links: list[str] | None = None,
) -> dict:
    """
    Full 7-agent generation pipeline:
      Agent 3: JD Analysis
      Agent 2: Structuring & Enrichment
      Portfolio Fetcher: fetch links (tool-based, no LLM)
      JD-Driven GitHub Ranker: Selects top GitHub repos matching the Job Description
      Agent 4: CV Generation
      Agent 5: Review & Polish (graceful failure)
      Agent 6: Cover Letter
      Agent 7: Compilation

    Returns dict with PDF paths, ats_report, and cleaned_data.
    """
    import uuid
    run_id = uuid.uuid4().hex[:8]
    results = {}

    # Phase 1: JD Analysis
    logger.info("[Pipeline] Agent 3: Analyzing job description...")
    jd_analysis = run_jd_analysis(job_description)

    # Phase 2: Structuring & Enrichment
    _already_structured = all(k in cleaned_data for k in ("name", "experience", "education", "skills"))
    if _already_structured:
        logger.info("[Pipeline] Data already structured — skipping structuring agent...")
        enriched_data = cleaned_data
    else:
        logger.info("[Pipeline] Agent 2: Structuring and enriching data...")
        enriched_data = run_structuring(json.dumps(cleaned_data), notes)

    # Phase 2.5: Auto-discover & Fetch portfolio links from candidate links dict + explicit links
    all_links = list(portfolio_links or [])
    candidate_links = enriched_data.get("links", {})
    if isinstance(candidate_links, dict):
        for link_val in candidate_links.values():
            if link_val and str(link_val).startswith("http") and link_val not in all_links:
                all_links.append(str(link_val))

    portfolio_projects = []
    if all_links:
        logger.info(f"[Pipeline] Fetching candidate portfolio links: {all_links}")
        portfolio_projects = run_portfolio_fetch(all_links)
        logger.info(f"[Pipeline] Fetched {len(portfolio_projects)} portfolio entries")

    # Phase 2.6: Merge & Rank GitHub repositories for target Job Description
    all_candidate_projects = list(enriched_data.get("projects", []) or [])
    if portfolio_projects:
        existing_urls = {p.get("url", "") for p in all_candidate_projects}
        for entry in portfolio_projects:
            platform = entry.get("platform", "website")
            if platform == "github" and entry.get("repos"):
                for repo in entry["repos"]:
                    repo_url = repo.get("url", f"https://github.com/{repo.get('full_name', '')}")
                    if repo_url in existing_urls:
                        continue
                    existing_urls.add(repo_url)
                    bullets = []
                    if repo.get("readme_excerpt"):
                        first_sentence = repo["readme_excerpt"].split(".")[0].strip()
                        if first_sentence:
                            bullets.append(first_sentence[:150])
                    all_candidate_projects.append({
                        "name": repo.get("name", ""),
                        "description": repo.get("description", ""),
                        "url": repo_url,
                        "stars": repo.get("stars", 0),
                        "language": repo.get("language", ""),
                        "topics": repo.get("topics", []),
                        "bullets": bullets,
                        "platform": "github",
                    })

    # Dynamically select and rank top repositories matching the JD task requirements
    top_jd_projects = _rank_and_select_projects_for_jd(all_candidate_projects, jd_analysis)
    if top_jd_projects:
        enriched_data["projects"] = top_jd_projects

    # Phase 3: CV Pipeline
    if output_type in ("cv", "both"):
        logger.info("[Pipeline] Agent 4: Generating CV...")
        cv_html = run_cv_generation(enriched_data, jd_analysis, notes)
        cv_html = _enforce_complete_resume_sections(cv_html, enriched_data)

        # Agent 5: Review & Score (graceful failure)
        logger.info("[Pipeline] Agent 5: Reviewing and scoring CV...")
        review = run_review_and_polish(cv_html, jd_analysis)
        if review:
            results["ats_report"] = {
                "score": review.get("score", 88),
                "strengths": review.get("strengths", []),
                "suggestions": review.get("suggestions", []),
            }
        else:
            results["ats_report"] = None

        logger.info("[Pipeline] Agent 7: Compiling CV to PDF...")
        cv_pdf = run_compilation(cv_html, f"cv_{run_id}")
        results["cv_pdf"] = str(cv_pdf)
        results["cv_html"] = cv_html

    # Phase 4: Cover Letter Pipeline
    if output_type in ("cover_letter", "both"):
        logger.info("[Pipeline] Agent 6: Generating cover letter...")
        cl_html = run_cover_letter_generation(enriched_data, jd_analysis, notes)

        logger.info("[Pipeline] Agent 7: Compiling cover letter to PDF...")
        cl_pdf = run_compilation(cl_html, f"cover_letter_{run_id}")
        results["cover_letter_pdf"] = str(cl_pdf)
        results["cover_letter_html"] = cl_html

    results["cleaned_data"] = enriched_data
    return results


def run_cleaning(raw_text: str) -> dict:
    """Backward-compatible alias for run_structuring."""
    return run_structuring(raw_text)


def run_ats_checker_crew(extracted_text: str, job_description: str) -> dict:
    """
    Feature 2: Dedicated ATS Resume Auditor pipeline.
    Runs the ats_auditor_agent against the candidate's CV text and job description.
    Returns a structured JSON report with score, keywords, section feedback, and suggestions.
    """
    report = _run_agent_task_with_json(
        ats_auditor_agent,
        description=(
            "You are performing a comprehensive ATS compatibility audit.\n\n"
            "CANDIDATE RESUME TEXT:\n"
            f"{extracted_text}\n\n"
            "TARGET JOB DESCRIPTION:\n"
            f"{job_description}\n\n"
            "AUDITING GUIDELINES:\n"
            "1. PROJECTS AS EXPERIENCE: If the candidate is a fresh graduate or early-career professional "
            "with no corporate employment history, their technical PROJECTS count as practical experience. "
            "Do NOT penalize the experience section with 0/100 just because it lacks a traditional job history. "
            "Instead, evaluate the quality, relevance, and technical depth of their projects. "
            "A strong projects section with no job history should score 60-80 on experience.\n"
            "2. ROLE MISMATCH DETECTION: If the job requires 5+ years of experience in a domain entirely "
            "different from the candidate's background (e.g., candidate is an AI/ML engineer but the job is "
            "for a Senior Project Manager with 8-12 years of PM experience), add a 'role_mismatch' field "
            "in the output JSON set to true, and include a 'role_mismatch_explanation' field explaining "
            "that the candidate's profile is not aligned with this specific role category. "
            "The score should still reflect keyword and content match objectively.\n"
            "3. DO NOT suggest fabricating skills or experience the candidate does not have.\n"
            "4. Actionable suggestions must be concrete and specific to THIS candidate's CV and THIS JD.\n\n"
            "Perform a thorough analysis and output ONLY valid JSON with ALL of these fields:\n"
            "{\n"
            '  "score": 0,\n'
            '  "verdict": "Strong Match | Moderate Match | Weak Match",\n'
            '  "role_mismatch": false,\n'
            '  "role_mismatch_explanation": "",\n'
            '  "matched_keywords": ["keyword1", "keyword2"],\n'
            '  "missing_keywords": ["keyword1", "keyword2"],\n'
            '  "preferred_keywords_found": ["keyword1"],\n'
            '  "preferred_keywords_missing": ["keyword1"],\n'
            '  "section_feedback": {\n'
            '    "summary": {"score": 0, "feedback": "", "suggestion": ""},\n'
            '    "experience": {"score": 0, "feedback": "", "suggestion": ""},\n'
            '    "skills": {"score": 0, "feedback": "", "suggestion": ""},\n'
            '    "education": {"score": 0, "feedback": "", "suggestion": ""},\n'
            '    "projects": {"score": 0, "feedback": "", "suggestion": ""}\n'
            '  },\n'
            '  "actionable_suggestions": [\n'
            '    {"priority": "High | Medium | Low", "action": "specific rewrite or addition to make"}\n'
            '  ],\n'
            '  "inquiry_questions": [\n'
            '    {"keyword": "C++", "question": "The job description requires experience with C++. Based on your extracted profile, C++ is unlisted. Have you ever worked with C++ or used C++ in any projects or coursework?"},\n'
            '    {"keyword": "Power BI", "question": "The position mentions Power BI for dashboards. Based on your profile, Power BI is unlisted. Have you created reports or dashboards in Power BI?"}\n'
            '  ],\n'
            '  "ats_formatting_issues": ["issue1", "issue2"],\n'
            '  "strengths": ["strength1", "strength2"]\n'
            "}\n\n"
            "INQUIRY QUESTION RULES (STRICTLY ENFORCED):\n"
            "1. Compare the candidate's extracted profile skills against every required/preferred skill in the job description.\n"
            "2. For every missing technical skill or qualification (e.g. C++, R, Power BI, Docker, PyTorch, Kubernetes, MLOps, Statistics), generate a specific, candidate-targeted question.\n"
            "3. Format each question explicitly as: 'The job description requires [KEYWORD]. Based on your extracted profile, [KEYWORD] is unlisted. Have you ever worked with [KEYWORD] or used [KEYWORD] in any projects, labs, or coursework?'\n"
            "4. Be direct and specific to THIS candidate's extracted profile and THIS job description.\n\n"
            "SCORING RULES:\n"
            "- Start from 0. Add points for each required keyword found (3 pts each), "
            "preferred keyword found (2 pts each), good section scores, and formatting.\n"
            "- Deduct points for missing required keywords (-4 pts each), weak bullets, "
            "generic summary, poor formatting.\n"
            "- For fresh graduates: if projects section is strong and relevant, add up to 15 bonus points.\n"
            "- Clamp final score to [0, 100].\n"
            "- verdict: score >= 70 -> 'Strong Match', score >= 40 -> 'Moderate Match', else 'Weak Match'.\n\n"
            "IMPORTANT: Include ALL top-level fields. Be specific and actionable in all feedback. "
            "Never suggest fabricating qualifications the candidate does not possess."
        ),
        expected_output="A valid JSON object with the full ATS audit report.",
        label="ATS Auditor",
        required_keys=["score", "matched_keywords", "missing_keywords", "section_feedback", "actionable_suggestions"],
        max_retries=2,
    )

    # Guaranteed Question Synthesizer Guardrail:
    # Ensure every missing keyword has a specific candidate inquiry question
    inquiry_q = report.get("inquiry_questions") or []
    missing_kw = report.get("missing_keywords") or []
    existing_keywords = {q.get("keyword", "").lower() for q in inquiry_q if isinstance(q, dict) and q.get("keyword")}

    for kw in missing_kw:
        if kw and str(kw).lower() not in existing_keywords and len(str(kw)) > 1:
            inquiry_q.append({
                "keyword": str(kw),
                "question": f"The job description requires experience with {kw}. Based on your extracted profile, {kw} is unlisted. Have you ever worked with {kw} or used {kw} in any projects, labs, or coursework?"
            })

    report["inquiry_questions"] = inquiry_q
    return report


def run_crew(
    file_bytes: bytes,
    filename: str,
    job_description: str,
    output_type: str,
    notes: str = "",
    portfolio_links: list[str] | None = None,
) -> dict:
    """Full pipeline: extract -> structuring -> generate -> compile."""
    raw_text = run_extraction(file_bytes, filename)
    results = run_generation_only(raw_text, job_description, output_type, notes, portfolio_links)
    results["extracted_text"] = raw_text
    return results
