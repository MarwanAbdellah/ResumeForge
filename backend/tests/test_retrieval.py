import base64
from unittest.mock import patch

from models.pipeline import ATSKeywordModel, EvidenceChunk
from retrieval import DiscoveryCoordinator
from retrieval.workers.github import GitHubWorker
from retrieval.workers.portfolio import PortfolioWorker


class TestGitHubWorker:
    @patch("tools.link_fetcher._fetch_json")
    def test_fetch_emits_one_chunk_per_repo(self, mock_fetch_json):
        readme_b64 = base64.b64encode(
            b"# ArabMedRAG\nA medical retrieval system built with Python, Pandas and SQL.\n"
            b"Dashboard: https://public.tableau.com/app/profile/marwan/viz/UdemyCourseAnalysisDashboard/Dashboard1"
        ).decode()
        mock_fetch_json.side_effect = [
            {"name": "Marwan", "bio": "AI Engineer", "public_repos": 2},
            [
                {
                    "name": "ArabMedRAG",
                    "full_name": "Marwan/ArabMedRAG",
                    "description": "Medical RAG with Python and SQL",
                    "html_url": "https://github.com/Marwan/ArabMedRAG",
                    "language": "Python",
                    "stargazers_count": 12,
                    "topics": ["nlp"],
                    "fork": False,
                },
                {
                    "name": "dashboard",
                    "full_name": "Marwan/dashboard",
                    "description": "Tableau dashboards for sales",
                    "html_url": "https://github.com/Marwan/dashboard",
                    "language": "JavaScript",
                    "stargazers_count": 3,
                    "topics": [],
                    "fork": False,
                },
            ],
            {"content": readme_b64},
            {"content": base64.b64encode(b"# Dashboard\nPower BI dashboards").decode()},
        ]

        chunks = GitHubWorker().fetch("https://github.com/Marwan", ATSKeywordModel())
        repo_chunks = [c for c in chunks if c.title in {"ArabMedRAG", "dashboard"}]

        assert len(repo_chunks) == 2
        arabmedrag = next(c for c in repo_chunks if c.title == "ArabMedRAG")
        # README text lands in the repo summary so it can be scored.
        assert "Pandas" in arabmedrag.summary or "SQL" in arabmedrag.summary
        assert "Python" in arabmedrag.technologies
        # URLs inside the README are captured as related links (e.g. Tableau).
        related = (arabmedrag.raw or {}).get("related_links") or []
        assert any("public.tableau.com" in url for url in related)

    def test_supports_github_urls(self):
        worker = GitHubWorker()
        assert worker.supports("https://github.com/user")
        assert not worker.supports("https://kaggle.com/user")


class TestPortfolioWorker:
    @patch("tools.link_fetcher.search_serper_web", return_value=[
        {"title": "Titanic EDA with Pandas", "link": "https://kaggle.com/me/titanic-eda", "snippet": "Cleaning data with pandas"},
    ])
    @patch("tools.link_fetcher._fetch_html", return_value="<html><head><title>Thin</title></head></html>")
    def test_kaggle_search_results_become_evidence_chunks(self, mock_html, mock_serper):
        chunks = PortfolioWorker().fetch("https://kaggle.com/me", ATSKeywordModel())
        search_chunks = [c for c in chunks if "Titanic" in c.title]
        assert search_chunks
        assert search_chunks[0].technologies  # inferred from title keywords


class TestCoordinatorScoring:
    def test_score_uses_repo_names_and_raw_text(self):
        chunk = EvidenceChunk(
            source="github",
            title="ArabMedRAG",
            technologies=["Python"],
            raw={"readme_excerpt": "Built with Pandas and SQL", "description": "medical RAG"},
        )
        keywords = ATSKeywordModel(required_keywords=["Pandas", "SQL", "Python"])
        assert DiscoveryCoordinator._score(chunk, keywords) == 3

    def test_score_counts_only_known_terms(self):
        chunk = EvidenceChunk(source="github", title="Nope", technologies=[])
        keywords = ATSKeywordModel(required_keywords=["Pandas"])
        assert DiscoveryCoordinator._score(chunk, keywords) == 0
