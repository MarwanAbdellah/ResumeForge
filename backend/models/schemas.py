"""Typed domain models shared by the API, CrewAI, and renderers."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _url_string(value: Any) -> str | None:
    return None if value is None or value == "" else str(value)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Certification(StrictModel):
    name: str = ""
    issuer: str = ""
    date: str = ""
    url: str | None = None

    _normalize_url = field_validator("url", mode="before")(_url_string)


class Skill(StrictModel):
    name: str = Field(min_length=1)
    category: str = ""
    proficiency: str = ""


class Language(StrictModel):
    name: str = Field(min_length=1)
    proficiency: str = ""


class Achievement(StrictModel):
    title: str = ""
    description: str = ""
    date: str = ""


class PortfolioEvidence(StrictModel):
    source_url: str | None = None
    platform: str = ""
    project_name: str = ""
    evidence: str = ""
    technologies: list[str] = Field(default_factory=list)
    verified: bool = False

    _normalize_source_url = field_validator("source_url", mode="before")(_url_string)


class Experience(StrictModel):
    title: str = ""
    company: str = ""
    location: str = ""
    dates: str = ""
    bullets: list[str] = Field(default_factory=list)


class Education(StrictModel):
    school: str = ""
    institution: str = ""
    degree: str = ""
    field: str = ""
    dates: str = ""
    details: str = ""


class Project(StrictModel):
    name: str = ""
    description: str = ""
    url: str | None = None
    demo_url: str | None = None
    bullets: list[str] = Field(default_factory=list)
    platform: str = ""

    _normalize_url = field_validator("url", mode="before")(_url_string)
    _normalize_demo_url = field_validator("demo_url", mode="before")(_url_string)


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    summary: str = ""
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    achievements: list[Achievement] = Field(default_factory=list)
    portfolio: list[PortfolioEvidence] = Field(default_factory=list)
    links: dict[str, str] = Field(default_factory=dict)

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, value: Any) -> Any:
        """Accept the old categorized object while storing typed skills."""
        if isinstance(value, dict):
            normalized = []
            for category, items in value.items():
                if not isinstance(category, str) or not isinstance(items, list):
                    raise ValueError("categorized skills must map strings to lists")
                for item in items:
                    if not isinstance(item, str):
                        raise ValueError("skill names must be strings")
                    if item.strip():
                        normalized.append({"name": item, "category": category})
            return normalized
        return value

    @field_validator("links", mode="before")
    @classmethod
    def normalize_links(cls, value: Any) -> Any:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("links must be an object")
        return {str(key): _url_string(url) for key, url in value.items() if _url_string(url)}


class Resume(Candidate):
    pass


class JobDescription(StrictModel):
    text: str = Field(min_length=1, max_length=50_000)
    title: str = ""
    requirements: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class CoverLetter(StrictModel):
    recipient: str = ""
    salutation: str = ""
    paragraphs: list[str] = Field(default_factory=list)
    signoff: str = ""


class ATSAction(StrictModel):
    priority: str = ""
    action: str


class SectionFeedback(StrictModel):
    section: str
    feedback: str


class InquiryQuestion(StrictModel):
    """A typed {keyword, question} pair for the pre-generation interview."""

    keyword: str = Field(min_length=1)
    question: str = Field(min_length=1)


class JobAnalysis(StrictModel):
    title: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    ats_keywords: list[str] = Field(default_factory=list)
    technical_stack: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)
    priorities: list[str] = Field(default_factory=list)
    resume_strategy: list[str] = Field(default_factory=list)


class ATSReport(StrictModel):
    score: int = Field(default=0, ge=0, le=100)
    verdict: str = ""
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    preferred_keywords_found: list[str] = Field(default_factory=list)
    preferred_keywords_missing: list[str] = Field(default_factory=list)
    section_feedback: list[SectionFeedback] = Field(default_factory=list)
    actionable_suggestions: list[ATSAction] = Field(default_factory=list)
    ats_formatting_issues: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    inquiry_questions: list[InquiryQuestion] = Field(default_factory=list)
