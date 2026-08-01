"""
Integration tests for the FastAPI backend endpoints.
Uses FastAPI TestClient with mocked crew functions to avoid LLM calls during CI.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Patch heavy imports before loading main
with (
    patch("crew.LLM", MagicMock()),
    patch("crew.Agent", MagicMock()),
    patch("crew.run_extraction", MagicMock(return_value="Sample resume text")),
    patch("crew.run_structuring", MagicMock(return_value={"name": "Jane Doe"})),
    patch("crew.run_generation_only", MagicMock(return_value={"cv_pdf": "cv_abc.pdf", "cover_letter_pdf": None, "cleaned_data": {}, "ats_report": None})),
    patch("crew.run_jd_analysis", MagicMock(return_value={"required_skills": [], "preferred_skills": [], "ats_keywords": [], "resume_strategy": {}})),
    patch("crew.run_ats_checker_crew", MagicMock(return_value={"score": 75, "verdict": "Strong Match", "matched_keywords": ["Python"], "missing_keywords": [], "preferred_keywords_found": [], "preferred_keywords_missing": [], "section_feedback": {}, "actionable_suggestions": [], "ats_formatting_issues": [], "strengths": ["Good keyword coverage"]})),
):
    from main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_check_returns_ok(self):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert "latex_compiler" in data


class TestExtractEndpoint:
    @patch("main.run_extraction", return_value="Extracted text content")
    def test_extract_txt_file(self, mock_extract):
        content = b"John Doe\nSoftware Engineer\nPython, React"
        res = client.post(
            "/api/extract",
            files={"file": ("cv.txt", content, "text/plain")},
        )
        assert res.status_code == 200
        data = res.json()
        assert "extracted_text" in data
        assert "filename" in data

    def test_extract_rejects_oversized_file(self):
        big_content = b"x" * (11 * 1024 * 1024)  # 11 MB
        res = client.post(
            "/api/extract",
            files={"file": ("cv.txt", big_content, "text/plain")},
        )
        assert res.status_code == 413


class TestCleanEndpoint:
    @patch("main.run_structuring", return_value={"name": "Jane Doe", "skills": {"languages": ["Python"]}})
    def test_clean_returns_cleaned_data(self, mock_struct):
        res = client.post(
            "/api/clean",
            json={"extracted_text": "Jane Doe\nPython developer with 5 years experience."},
        )
        assert res.status_code == 200
        data = res.json()
        assert "cleaned_data" in data

    def test_clean_rejects_empty_text(self):
        res = client.post("/api/clean", json={"extracted_text": "   "})
        assert res.status_code == 400


class TestATSCheckEndpoint:
    @patch(
        "main.run_ats_checker_crew",
        return_value={
            "score": 82,
            "verdict": "Strong Match",
            "matched_keywords": ["Python", "FastAPI"],
            "missing_keywords": ["Docker"],
            "preferred_keywords_found": ["React"],
            "preferred_keywords_missing": [],
            "section_feedback": {},
            "actionable_suggestions": [{"priority": "High", "action": "Add Docker experience"}],
            "ats_formatting_issues": [],
            "strengths": ["Strong Python background"],
        },
    )
    def test_ats_check_returns_full_report(self, mock_crew):
        enriched = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "(+1) 555-1234",
            "location": "New York, NY",
            "summary": "Experienced Python developer.",
            "experience": [{"title": "Engineer", "company": "Acme", "location": "NY", "dates": "2020-Present", "bullets": ["Built APIs with FastAPI"]}],
            "education": [{"school": "MIT", "degree": "BSc", "field": "CS", "dates": "2016-2020", "details": ""}],
            "skills": {"languages": ["Python", "React"], "tools": ["FastAPI", "PostgreSQL"]},
            "projects": [],
            "certifications": [],
        }
        res = client.post(
            "/api/ats-check",
            json={
                "job_description": "We need a Python developer with FastAPI and Docker experience.",
                "enriched_data": enriched,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert "score" in data
        assert "verdict" in data
        assert "matched_keywords" in data
        assert "missing_keywords" in data
        assert "actionable_suggestions" in data

    def test_ats_check_rejects_empty_jd(self):
        res = client.post(
            "/api/ats-check",
            json={"job_description": "   ", "enriched_data": {"name": "Jane"}},
        )
        assert res.status_code == 400

    def test_ats_check_rejects_empty_enriched_data(self):
        res = client.post(
            "/api/ats-check",
            json={"job_description": "We need a Python engineer.", "enriched_data": {}},
        )
        assert res.status_code == 400


class TestGapInquireEndpoint:
    @patch("main.run_jd_analysis", return_value={"required_skills": ["Docker"], "technical_stack": []})
    @patch(
        "main.run_ats_checker_crew",
        return_value={
            "score": 70,
            "verdict": "Moderate Match",
            "matched_keywords": ["Python"],
            "missing_keywords": ["Docker"],
            "preferred_keywords_found": [],
            "preferred_keywords_missing": [],
            "section_feedback": {},
            "actionable_suggestions": [],
            "ats_formatting_issues": [],
            "strengths": [],
            "inquiry_questions": [],
        },
    )
    @patch("main.run_structuring", return_value={"name": "Jane Doe", "summary": "Python dev with Docker exposure"})
    def test_gap_inquire_with_unlisted_experience(self, mock_struct, mock_ats, mock_jd):
        # Exercises the json.dumps merge path that previously raised NameError
        res = client.post(
            "/api/ats-gap-inquire",
            json={
                "job_description": "We need a Python developer with Docker experience.",
                "enriched_data": {"name": "Jane Doe", "summary": "Python dev"},
                "unlisted_experience": "I used Docker in a Udemy course project.",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert "recalibrated_data" in data
        assert "inquiry_questions" in data

    def test_gap_inquire_rejects_empty_jd(self):
        res = client.post(
            "/api/ats-gap-inquire",
            json={"job_description": "   ", "enriched_data": {"name": "Jane"}},
        )
        assert res.status_code == 400


class TestPreviewEndpoint:
    def test_preview_rejects_path_traversal(self):
        res = client.get("/api/preview/../etc/passwd.pdf")
        assert res.status_code in (400, 404, 422)

    def test_preview_rejects_non_pdf(self):
        res = client.get("/api/preview/malicious.exe")
        assert res.status_code in (400, 422)

    def test_preview_returns_404_for_missing_file(self):
        res = client.get("/api/preview/cv_notexist.pdf")
        assert res.status_code == 404


class TestDownloadEndpoint:
    def test_download_rejects_invalid_filename(self):
        # Filenames with special chars get rejected at various levels (400/404/422)
        res = client.get("/api/download/cv;rm -rf /.pdf")
        assert res.status_code in (400, 404, 422)

    def test_download_returns_404_for_missing_file(self):
        res = client.get("/api/download/cv_notexist.pdf")
        assert res.status_code == 404
