"""
CV Magic Agent Tools

Tools for job scouring based on user CVs/resumes.
These are EXECUTION tools — bidding is handled by shared bidding_tools.
"""

import os
import json
import base64
import logging
from typing import Any, Dict, List, Optional

from pydantic import Field

from ..shared.tool_base import BaseTool

logger = logging.getLogger(__name__)


class ScourJobsTool(BaseTool):
    """
    Tool to search job boards based on user CV/resume and preferences.
    Returns scored and filtered job listings.
    """
    name: str = "scour_jobs"
    description: str = """
    Search job boards based on user resume/CV documents and job preferences.
    
    Analyzes the provided documents to extract skills and experience,
    then searches whitelisted job boards (LinkedIn, Indeed, etc.) and
    returns scored/filtered job listings ranked by relevance.
    
    Returns up to num_openings jobs with relevance scores and application tips.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "document_base64": {
                "type": "string",
                "description": "Base64-encoded CV/resume document (PDF, DOCX, or TXT)"
            },
            "document_filename": {
                "type": "string",
                "description": "Original filename of the document (e.g., 'resume.pdf')"
            },
            "job_title": {
                "type": "string",
                "description": "Target job title to search for (e.g., 'Software Engineer')"
            },
            "location": {
                "type": "string",
                "description": "Target location/region (e.g., 'United Kingdom', 'London')"
            },
            "seniority": {
                "type": "string",
                "description": "Seniority level: intern, junior, mid, senior, lead"
            },
            "remote": {
                "type": "boolean",
                "description": "Whether to filter for remote positions"
            },
            "employment_type": {
                "type": "string",
                "description": "Employment type: full-time, part-time, contract, internship"
            },
            "include_keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Keywords to include in search"
            },
            "exclude_keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Keywords to exclude from results"
            },
            "num_openings": {
                "type": "integer",
                "description": "Target number of job openings to return (default 100)"
            }
        },
        "required": ["document_base64", "document_filename", "job_title", "location"]
    }

    async def execute(
        self,
        document_base64: str,
        document_filename: str,
        job_title: str,
        location: str,
        seniority: Optional[str] = None,
        remote: Optional[bool] = None,
        employment_type: Optional[str] = None,
        include_keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
        num_openings: int = 100
    ) -> str:
        """Execute job scouring based on CV and preferences"""
        try:
            from .services.job_scourer import scour_jobs_with_brightdata, build_default_job_board_search_urls
            from .services.openai_scour_jobs import (
                extract_user_profile_from_text,
                score_jobs_with_embeddings,
                filter_jobs_by_preferences,
                enrich_jobs_with_openai,
            )
            from .services.document_text import extract_text_from_bytes
            from .services.models import UserProfileForScouring, ScourPreferences
        except ImportError as e:
            return json.dumps({
                "success": False,
                "error": f"CV Magic services not initialized: {e}"
            })

        try:
            # Decode document
            doc_bytes = base64.b64decode(document_base64)
            
            # Extract text from document
            extraction = extract_text_from_bytes(
                data=doc_bytes,
                filename=document_filename,
                content_type=None
            )
            
            if not extraction.text:
                return json.dumps({
                    "success": False,
                    "error": "Could not extract text from document"
                })

            # Build preferences
            preferences = {
                "job_title": job_title,
                "location": location,
                "seniority": seniority,
                "remote": remote,
                "employment_type": employment_type,
                "include_keywords": include_keywords or [],
                "exclude_keywords": exclude_keywords or [],
            }

            # Extract user profile from document text
            user_profile = extract_user_profile_from_text(
                text=extraction.text[:50000],  # Limit input size
                preferences=preferences,
                existing_profile={},
                confirmed_attributes={},
            )

            # Build search URLs
            search_urls = build_default_job_board_search_urls(
                user_profile=user_profile,
                preferences=preferences
            )

            # Scour jobs from job boards
            raw_jobs, warnings = scour_jobs_with_brightdata(
                user_profile=user_profile,
                preferences=preferences,
                search_urls=search_urls,
                target_openings=num_openings,
                fetch_mode="auto"
            )

            # Score and filter jobs
            filtered_jobs = score_jobs_with_embeddings(
                user_profile=user_profile,
                jobs=raw_jobs,
                relevance_threshold=60
            )
            filtered_jobs = filter_jobs_by_preferences(
                preferences=preferences,
                jobs=filtered_jobs
            )

            # Enrich with AI analysis
            enriched = enrich_jobs_with_openai(
                user_profile=user_profile,
                preferences=preferences,
                jobs=filtered_jobs[:num_openings],
                location=location
            )

            return json.dumps({
                "success": True,
                "user_profile": user_profile.model_dump() if hasattr(user_profile, 'model_dump') else dict(user_profile),
                "jobs": [j.model_dump() if hasattr(j, 'model_dump') else dict(j) for j in enriched],
                "queries": search_urls,
                "meta": {
                    "raw_jobs_found": len(raw_jobs),
                    "filtered_jobs": len(filtered_jobs),
                    "returned_jobs": len(enriched),
                },
                "warnings": warnings
            })

        except Exception as e:
            logger.exception("Error scouring jobs: %s", e)
            return json.dumps({
                "success": False,
                "error": str(e)
            })


class ExtractProfileTool(BaseTool):
    """
    Tool to extract candidate profile from a CV/resume document.
    """
    name: str = "extract_profile"
    description: str = """
    Extract a structured candidate profile from a CV/resume document.
    
    Uses AI to parse the document and extract:
    - Skills and technologies
    - Years of experience
    - Education background
    - Project highlights
    - Links (GitHub, LinkedIn, portfolio)
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "document_base64": {
                "type": "string",
                "description": "Base64-encoded CV/resume document"
            },
            "document_filename": {
                "type": "string",
                "description": "Original filename (e.g., 'resume.pdf')"
            }
        },
        "required": ["document_base64", "document_filename"]
    }

    async def execute(
        self,
        document_base64: str,
        document_filename: str
    ) -> str:
        """Extract profile from CV document"""
        try:
            from .services.document_text import extract_text_from_bytes
            from .services.openai_scour_jobs import extract_user_profile_from_text
        except ImportError:
            return json.dumps({
                "success": False,
                "error": "CV Magic services not initialized"
            })

        try:
            doc_bytes = base64.b64decode(document_base64)
            
            extraction = extract_text_from_bytes(
                data=doc_bytes,
                filename=document_filename,
                content_type=None
            )
            
            if not extraction.text:
                return json.dumps({
                    "success": False,
                    "error": "Could not extract text from document"
                })

            user_profile = extract_user_profile_from_text(
                text=extraction.text[:50000],
                preferences={},
                existing_profile={},
                confirmed_attributes={},
            )

            return json.dumps({
                "success": True,
                "profile": user_profile.model_dump() if hasattr(user_profile, 'model_dump') else dict(user_profile),
                "extraction_method": extraction.method
            })

        except Exception as e:
            logger.exception("Error extracting profile: %s", e)
            return json.dumps({
                "success": False,
                "error": str(e)
            })


class GetJobDetailsTool(BaseTool):
    """
    Tool to fetch detailed information about a specific job listing.
    """
    name: str = "get_job_details"
    description: str = """
    Fetch detailed information about a specific job listing URL.
    
    Scrapes the job page to get full description, requirements,
    company info, and application instructions.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "job_url": {
                "type": "string",
                "description": "URL of the job listing to fetch details for"
            }
        },
        "required": ["job_url"]
    }

    async def execute(self, job_url: str) -> str:
        """Fetch job details from URL"""
        try:
            from .services.brightdata_http import brightdata_get
            from .services.brightdata_agent_tools import parse_html_payload
        except ImportError:
            return json.dumps({
                "success": False,
                "error": "BrightData services not initialized"
            })

        try:
            html = brightdata_get(job_url)
            if not html:
                return json.dumps({
                    "success": False,
                    "error": "Could not fetch job page"
                })

            job_data = parse_html_payload(html, job_url)
            
            return json.dumps({
                "success": True,
                "job_url": job_url,
                "details": job_data
            })

        except Exception as e:
            logger.exception("Error fetching job details: %s", e)
            return json.dumps({
                "success": False,
                "error": str(e)
            })


def create_cv_magic_tools() -> List[BaseTool]:
    """Create all CV Magic agent tools"""
    return [
        ScourJobsTool(),
        ExtractProfileTool(),
        GetJobDetailsTool(),
    ]
