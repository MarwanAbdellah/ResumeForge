import io
import re
import pdfplumber
from docx import Document


def extract_pdf(file_bytes: bytes) -> str:
    """Extract text and hyperlinks from a PDF using pdfplumber."""
    text_parts = []
    all_urls = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

            # Extract URLs from hyperlink annotations
            if hasattr(page, "annots") and page.annots:
                for annot in page.annots:
                    url = None
                    # Direct URI
                    if annot.get("uri"):
                        url = annot["uri"]
                    # Action-based URI (common in PDFs)
                    elif annot.get("A") and isinstance(annot["A"], dict):
                        url = annot["A"].get("URI")
                    if url and url.startswith("http") and url not in all_urls:
                        all_urls.append(url)

    result = "\n\n".join(text_parts)

    # Append discovered URLs so the structuring agent can capture them
    if all_urls:
        result += "\n\n--- DISCOVERED LINKS ---\n"
        for url in all_urls:
            result += f"{url}\n"

    return result


def extract_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX using python-docx."""
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Route to the correct extractor based on file extension."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_pdf(file_bytes)
    elif lower.endswith(".docx"):
        return extract_docx(file_bytes)
    elif lower.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file type: {filename}")


# ── Text repair for extraction artifacts ───────────────────────────────────

# Known corrupted concatenations (missing spaces / broken hyphens) that appear
# when PDF text extraction or transcription merges tokens. Longest-first.
_TEXT_REPAIRS = [
    (
        "Real-timevoiceagentwithLiveKitandMCPsupportingEnglish-Arabiccode-switchingandlow-latencyaudiostream-ing",
        "Real-time voice agent with LiveKit and MCP supporting English-Arabic code-switching and low-latency audio streaming",
    ),
    (
        "FastAPIbackendservingaTelegrambotandwebsite",
        "FastAPI backend serving a Telegram bot and website",
    ),
    (
        "deployedonAWSEC2withautomatedtestinganddeployment",
        "deployed on AWS EC2 with automated testing and deployment",
    ),
    ("English-Arabiccode-switching", "English-Arabic code-switching"),
    ("code-switchingandlow-latency", "code-switching and low-latency"),
    ("low-latencyaudiostream-ing", "low-latency audio streaming"),
    ("audiostream-ing", "audio streaming"),
    ("PowerBI", "Power BI"),
    ("TableauPublic", "Tableau Public"),
    ("NaturalLanguageProcessing", "Natural Language Processing"),
    ("LargeLanguageModels", "Large Language Models"),
    ("LargeLanguageModel", "Large Language Model"),
    ("MachineLearning", "Machine Learning"),
    ("DeepLearning", "Deep Learning"),
    ("ComputerVision", "Computer Vision"),
    ("DataAnalysis", "Data Analysis"),
    ("DataAnalytics", "Data Analytics"),
    ("DataVisualization", "Data Visualization"),
    ("TimeSeries", "Time Series"),
    ("FeatureEngineering", "Feature Engineering"),
    ("InformationRetrieval", "Information Retrieval"),
]

_ZERO_WIDTH = {0x00AD, 0x200B, 0x200C, 0x200D, 0xFEFF, 0x2060}


def repair_extracted_text(text: str) -> str:
    """Fix common extraction artifacts (soft hyphens, glued words, broken spacing)."""
    if not text:
        return text

    # 1. Drop soft hyphens and zero-width characters.
    text = "".join(ch for ch in text if ord(ch) not in _ZERO_WIDTH)

    # 2. Apply curated phrase repairs (longest first).
    for corrupted, repaired in sorted(_TEXT_REPAIRS, key=lambda pair: len(pair[0]), reverse=True):
        text = text.replace(corrupted, repaired)

    # 3. Best-effort space insertion inside very long alphanumeric runs
    #    (camelCase boundaries and acronym-to-word boundaries).
    return "".join(
        _insert_run_spaces(token) if re.fullmatch(r"[A-Za-z0-9]{19,}", token) else token
        for token in re.split(r"([A-Za-z0-9]+)", text)
    )


def _insert_run_spaces(token: str) -> str:
    """Insert spaces at camelCase / acronym boundaries inside one glued run."""
    out: list[str] = []
    for i, char in enumerate(token):
        boundary = False
        if i > 0:
            prev = token[i - 1]
            nxt = token[i + 1] if i + 1 < len(token) else ""
            prev_lower = prev.islower() or prev.isdigit()
            nxt_lower = bool(nxt) and (nxt.islower() or nxt.isdigit())
            # camelCase boundary: lower -> Upper -> lower
            if prev_lower and char.isupper() and nxt_lower:
                boundary = True
            # acronym-to-word boundary: lower/digit -> UpperRun -> lower
            elif (
                i >= 2
                and prev_lower
                and char.isupper()
                and nxt_lower
                and token[i - 2].isupper()
            ):
                boundary = True
        if boundary:
            out.append(" ")
        out.append(char)
    return "".join(out)


def extract_urls(text: str, file_bytes: bytes = b"", filename: str = "") -> list[str]:
    """Extract all HTTP/HTTPS URLs from text and PDF annotations."""
    urls = []
    
    # 1. Regex URL extraction from text
    url_pattern = r'https?://[^\s<>"\')]+|www\.[^\s<>"\')]+'
    for match in re.findall(url_pattern, text):
        clean_url = match.rstrip(".,;)\"\']")
        if not clean_url.startswith("http"):
            clean_url = f"https://{clean_url}"
        if clean_url not in urls:
            urls.append(clean_url)

    # 2. PDF annotations if PDF
    if filename.lower().endswith(".pdf") and file_bytes:
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    if hasattr(page, "annots") and page.annots:
                        for annot in page.annots:
                            url = None
                            if annot.get("uri"):
                                url = annot["uri"]
                            elif annot.get("A") and isinstance(annot["A"], dict):
                                url = annot["A"].get("URI")
                            if url:
                                clean_url = url.strip().rstrip(".,;)\"\']")
                                if clean_url.startswith("http") and clean_url not in urls:
                                    urls.append(clean_url)
        except Exception:
            pass

    return urls


# ── Extraction diagnostics ─────────────────────────────────────────────────

PLATFORM_MARKERS = {
    "github": ("github.com", ("github",)),
    "kaggle": ("kaggle.com", ("kaggle",)),
    "linkedin": ("linkedin.com", ("linkedin",)),
    "huggingface": ("huggingface.co", ("huggingface", "hugging face")),
}


def _pdf_stats(file_bytes: bytes) -> tuple[int, int]:
    """Return (page_count, hyperlink_annotation_count) for a PDF."""
    page_count = 0
    annotations = 0
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                if hasattr(page, "annots") and page.annots:
                    annotations += len(page.annots)
    except Exception:
        pass
    return page_count, annotations


def per_source_status(text: str, urls: list[str]) -> dict[str, dict[str, str]]:
    """Per-platform extraction status so the UI can surface missing links."""
    lower = text.lower()
    result: dict[str, dict[str, str]] = {}
    for platform, (domain, words) in PLATFORM_MARKERS.items():
        url_found = any(domain in u.lower() for u in urls)
        word_found = any(word in lower for word in words)
        if url_found:
            result[platform] = {
                "status": "url_found",
                "detail": f"Found a {platform} URL in the document.",
            }
        elif word_found:
            result[platform] = {
                "status": "word_only",
                "detail": (
                    f"{platform.capitalize()} is mentioned in the text but no URL was found. "
                    "Add the link manually below to enrich the profile."
                ),
            }
        else:
            result[platform] = {"status": "not_found", "detail": ""}
    return result


def build_extraction_diagnostics(
    text: str, urls: list[str], file_bytes: bytes = b"", filename: str = ""
) -> dict:
    """Diagnostics for the /api/extract response."""
    page_count = 0
    annotations = 0
    if filename.lower().endswith(".pdf") and file_bytes:
        page_count, annotations = _pdf_stats(file_bytes)
    else:
        page_count = 1
    return {
        "page_count": page_count,
        "character_count": len(text),
        "hyperlink_annotations": annotations,
        "detected_urls": urls,
        "sources": per_source_status(text, urls),
    }
