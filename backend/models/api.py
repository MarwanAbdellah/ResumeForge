"""HTTP request contracts kept separate from domain pipeline models."""

from typing import Literal

from pydantic import BaseModel, Field


class CleanRequest(BaseModel):
    extracted_text: str = Field(min_length=1, max_length=100_000)
    portfolio_links: list[str] = Field(default_factory=list, max_length=10)


class GenerateRequest(BaseModel):
    cleaned_data: dict = Field(min_length=1)
    job_description: str = Field(min_length=1, max_length=50_000)
    output_type: Literal["cv", "cover_letter", "both"] = "both"
    notes: str = Field(default="", max_length=10_000)
    portfolio_links: list[str] = Field(default_factory=list, max_length=10)


class AnalyzeRequest(BaseModel):
    job_description: str = Field(min_length=10, max_length=50_000)


class ATSCheckRequest(BaseModel):
    job_description: str = Field(max_length=50_000)
    enriched_data: dict
    portfolio_links: list[str] = Field(default_factory=list, max_length=10)


class GapInquireRequest(BaseModel):
    job_description: str
    enriched_data: dict
    unlisted_experience: str = ""
