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
