"""Official CrewAI declarative crew definition for the ResumeForge pipeline."""

from pathlib import Path

from crewai import Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task

from models.pipeline import ATSKeywordModel, CoverLetterReviewModel, ResumeModel
from models.schemas import ATSReport, Candidate, CoverLetter, JobAnalysis, PortfolioEvidence

CONFIG_DIR = Path(__file__).parent.parent / "config"


@CrewBase
class ResumeForgeCrew:
    """CrewAI's config-backed agent/task graph.

    Task contexts mirror the data flow so each task receives the typed upstream
    result. The full sequential crew is retained for CrewAI convention; the
    runtime executes individual typed tasks concurrently via the DAG engine.
    """

    agents_config = str(CONFIG_DIR / "agents.yaml")
    tasks_config = str(CONFIG_DIR / "tasks.yaml")

    TASK_OUTPUT_MODELS = {
        "extract_resume": Candidate,
        "structure_resume": Candidate,
        "analyze_job": JobAnalysis,
        "extract_ats_keywords": ATSKeywordModel,
        "generate_resume": ResumeModel,
        "generate_cover_letter": CoverLetter,
        "review_ats": ATSReport,
        "review_cover_letter": CoverLetterReviewModel,
        "analyze_portfolio": PortfolioEvidence,
    }

    TASK_AGENTS = {
        "extract_resume": "resume_extraction_agent",
        "structure_resume": "resume_structuring_agent",
        "analyze_job": "job_description_agent",
        "extract_ats_keywords": "ats_keyword_agent",
        "generate_resume": "resume_generation_agent",
        "generate_cover_letter": "cover_letter_agent",
        "review_ats": "ats_review_agent",
        "review_cover_letter": "cover_letter_review_agent",
        "analyze_portfolio": "portfolio_analysis_agent",
    }

    def __init__(self, llm: LLM | None = None):
        self.llm = llm

    def _agent(self, name: str):
        from crewai import Agent

        return Agent(config=self.agents_config[name], llm=self.llm, verbose=False)

    @agent
    def resume_extraction_agent(self):
        return self._agent("resume_extraction_agent")

    @agent
    def resume_structuring_agent(self):
        return self._agent("resume_structuring_agent")

    @agent
    def job_description_agent(self):
        return self._agent("job_description_agent")

    @agent
    def ats_keyword_agent(self):
        return self._agent("ats_keyword_agent")

    @agent
    def resume_generation_agent(self):
        return self._agent("resume_generation_agent")

    @agent
    def cover_letter_agent(self):
        return self._agent("cover_letter_agent")

    @agent
    def ats_review_agent(self):
        return self._agent("ats_review_agent")

    @agent
    def cover_letter_review_agent(self):
        return self._agent("cover_letter_review_agent")

    @agent
    def portfolio_analysis_agent(self):
        return self._agent("portfolio_analysis_agent")

    @task
    def extract_resume(self):
        return Task(config=self.tasks_config["extract_resume"], agent=self.resume_extraction_agent(), output_pydantic=Candidate)

    @task
    def structure_resume(self):
        return Task(config=self.tasks_config["structure_resume"], agent=self.resume_structuring_agent(), output_pydantic=Candidate, context=[self.extract_resume()])

    @task
    def analyze_job(self):
        return Task(config=self.tasks_config["analyze_job"], agent=self.job_description_agent(), output_pydantic=JobAnalysis)

    @task
    def extract_ats_keywords(self):
        return Task(config=self.tasks_config["extract_ats_keywords"], agent=self.ats_keyword_agent(), output_pydantic=ATSKeywordModel)

    @task
    def generate_resume(self):
        return Task(config=self.tasks_config["generate_resume"], agent=self.resume_generation_agent(), output_pydantic=ResumeModel, context=[self.analyze_job()])

    # Internal compatibility alias while callers migrate to the clearer name.
    def optimize_resume(self):
        return self.generate_resume()

    @task
    def generate_cover_letter(self):
        return Task(config=self.tasks_config["generate_cover_letter"], agent=self.cover_letter_agent(), output_pydantic=CoverLetter)

    @task
    def review_ats(self):
        return Task(config=self.tasks_config["review_ats"], agent=self.ats_review_agent(), output_pydantic=ATSReport)

    @task
    def review_cover_letter(self):
        return Task(config=self.tasks_config["review_cover_letter"], agent=self.cover_letter_review_agent(), output_pydantic=CoverLetterReviewModel)

    @task
    def analyze_portfolio(self):
        return Task(config=self.tasks_config["analyze_portfolio"], agent=self.portfolio_analysis_agent(), output_pydantic=PortfolioEvidence)

    def isolated_task(self, name: str):
        """Build one typed task for service/DAG-level execution without legacy context."""
        return Task(
            config=self.tasks_config[name],
            agent=self._agent(self.TASK_AGENTS[name]),
            output_pydantic=self.TASK_OUTPUT_MODELS[name],
        )

    @crew
    def crew(self):
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=False,
        )
