"""
Pydantic models for CV Magic job scouring.

Simplified from the original cv-magic backend models.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScourDifficulty(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ScourCompetitiveness(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ScourPreferences(BaseModel):
    """Job search preferences"""
    job_title: Optional[str] = None
    seniority: Optional[str] = None  # e.g., intern|junior|mid|senior|lead
    remote: Optional[bool] = None
    salary_min_gbp: Optional[int] = None
    location: Optional[str] = None  # e.g. "United Kingdom", "Germany"
    experience_years_min: Optional[int] = None
    experience_years_max: Optional[int] = None
    employment_type: Optional[str] = None  # e.g., full-time|part-time|contract|internship
    include_keywords: Optional[List[str]] = None
    exclude_keywords: Optional[List[str]] = None
    posted_within_days: Optional[int] = None
    visa_sponsorship_required: Optional[bool] = None
    fetch_mode: Optional[str] = None  # auto|http|browser
    portfolio_url: Optional[str] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None

    model_config = {"extra": "allow"}


class UserProfileForScouring(BaseModel):
    """Extracted user profile from CV/resume"""
    skills: List[str] = Field(default_factory=list)
    experience_years: int = 0
    education: str = ""
    projects: List[str] = Field(default_factory=list)
    links: Dict[str, Any] = Field(default_factory=dict)
    preferences: Dict[str, Any] = Field(default_factory=dict)


class ScouredJob(BaseModel):
    """A job listing found during scouring"""
    title: str
    company: str = ""
    location: str = ""
    salary_range: str = ""
    posted_date: str = ""
    url: str = ""
    source_domain: str = ""
    description: str = ""
    requirements: str = ""

    # AI-generated scores
    relevance_index: int = 0
    difficulty: Optional[ScourDifficulty] = None
    competitiveness: Optional[ScourCompetitiveness] = None
    rationale: str = ""
    application_tips: str = ""


class ScourJobsResponse(BaseModel):
    """Response from job scouring"""
    user_profile: UserProfileForScouring
    queries: List[str] = Field(default_factory=list)
    jobs: List[ScouredJob] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
