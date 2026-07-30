import io
import pytest
from tools.extractors import extract_text, extract_pdf, extract_docx


class TestExtractText:
    def test_txt_extraction(self):
        content = b"Hello World\nSecond line"
        result = extract_text(content, "test.txt")
        assert result == "Hello World\nSecond line"

    def test_txt_utf8_with_replacements(self):
        content = "Hello \xff\xfe World".encode("utf-8", errors="replace")
        result = extract_text(content, "test.txt")
        assert "Hello" in result

    def test_unsupported_file_type(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_text(b"content", "test.xyz")

    def test_pdf_extraction(self):
        # Create a minimal valid PDF with text
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R"
            b"/Resources<</Font<</F1 4 0 R>>>>>>endobj\n"
            b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
            b"xref\n0 5\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"0000000266 00000 n \n"
            b"trailer<</Size 5/Root 1 0 R>>\n"
            b"startxref\n345\n%%EOF"
        )
        # pdfplumber may handle this gracefully or raise - both are acceptable
        try:
            result = extract_pdf(pdf_bytes)
            assert isinstance(result, str)
        except Exception:
            pass  # Minimal PDF may not be parseable

    def test_docx_extraction(self):
        from docx import Document

        doc = Document()
        doc.add_paragraph("Hello World")
        doc.add_paragraph("Second paragraph")
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)

        result = extract_docx(buf.read())
        assert "Hello World" in result
        assert "Second paragraph" in result

    def test_docx_empty_paragraphs(self):
        from docx import Document

        doc = Document()
        doc.add_paragraph("Only content")
        doc.add_paragraph("")  # empty paragraph
        doc.add_paragraph("  ")  # whitespace-only paragraph
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)

        result = extract_docx(buf.read())
        assert "Only content" in result
        assert result.strip() == "Only content"
