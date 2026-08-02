"""Official CrewAI declarative crew definition for the ResumeForge pipeline."""

from pathlib import Path

from crewai import Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task

from models.schemas import ATSReport, Candidate, CoverLetter, JobAnalysis, PortfolioEvidence


CONFIG_DIR = Path(__file__).parent.parent / "config"


@CrewBase
class ResumeForgeCrew:
    """CrewAI's config-backed agent/task graph.

    The task contexts intentionally mirror the data flow instead of relying on
    task ordering alone, so each task receives the typed upstream result.
    """

    agents_config = str(CONFIG_DIR / "agents.yaml")
    tasks_config = str(CONFIG_DIR / "tasks.yaml")

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
    def resume_optimization_agent(self):
        return self._agent("resume_optimization_agent")

    @agent
    def cover_letter_agent(self):
        return self._agent("cover_letter_agent")

    @agent
    def ats_review_agent(self):
        return self._agent("ats_review_agent")

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
    def optimize_resume(self):
        return Task(config=self.tasks_config["optimize_resume"], agent=self.resume_optimization_agent(), output_pydantic=Candidate, context=[self.structure_resume(), self.analyze_job()])

    @task
    def generate_cover_letter(self):
        return Task(config=self.tasks_config["generate_cover_letter"], agent=self.cover_letter_agent(), output_pydantic=CoverLetter, context=[self.optimize_resume(), self.analyze_job()])

    @task
    def review_ats(self):
        return Task(config=self.tasks_config["review_ats"], agent=self.ats_review_agent(), output_pydantic=ATSReport, context=[self.optimize_resume(), self.analyze_job()])

    @task
    def analyze_portfolio(self):
        return Task(config=self.tasks_config["analyze_portfolio"], agent=self.portfolio_analysis_agent(), output_pydantic=PortfolioEvidence)

    def isolated_task(self, name: str):
        """Build one typed task for service-level execution without legacy context."""
        agent_names = {
            "extract_resume": "resume_extraction_agent",
            "structure_resume": "resume_structuring_agent",
            "analyze_job": "job_description_agent",
            "optimize_resume": "resume_optimization_agent",
            "generate_cover_letter": "cover_letter_agent",
            "review_ats": "ats_review_agent",
            "analyze_portfolio": "portfolio_analysis_agent",
        }
        output_models = {
            "extract_resume": Candidate,
            "structure_resume": Candidate,
            "analyze_job": JobAnalysis,
            "optimize_resume": Candidate,
            "generate_cover_letter": CoverLetter,
            "review_ats": ATSReport,
            "analyze_portfolio": PortfolioEvidence,
        }
        return Task(
            config=self.tasks_config[name],
            agent=self._agent(agent_names[name]),
            output_pydantic=output_models[name],
        )

    @crew
    def crew(self):
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=False,
        )
