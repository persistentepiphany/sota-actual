"""
OpenAI-powered job analysis for CV Magic.

Extracts user profiles, scores jobs, and enriches results with AI.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .config import get_settings
from .models import ScouredJob, UserProfileForScouring

logger = logging.getLogger(__name__)


# ─── OpenAI Utilities ────────────────────────────────────────

def _openai_client():
    """Get OpenAI client."""
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError("Missing OpenAI dependency. Install `openai`.") from e
    
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _openai_json(
    *,
    client: Any,
    model: str,
    instructions: str,
    input_text: str,
    schema: Optional[Dict[str, Any]] = None,
    schema_name: str = "payload",
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """Call OpenAI and parse JSON response."""
    messages = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": input_text}
    ]
    
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"} if schema else None,
    )
    
    content = response.choices[0].message.content or "{}"
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _relevance_from_cos(sim: float) -> int:
    """Convert cosine similarity to 0-100 relevance score."""
    return max(0, min(100, int((sim + 1) * 50)))


# ─── Profile Extraction ──────────────────────────────────────

def extract_user_profile_from_text(
    *,
    text: str,
    preferences: Dict[str, Any],
    existing_profile: Optional[Dict[str, Any]] = None,
    confirmed_attributes: Optional[Dict[str, Any]] = None,
) -> UserProfileForScouring:
    """
    Uses OpenAI to extract a normalized user profile for job scouring.
    """
    settings = get_settings()
    client = _openai_client()

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "skills": {"type": "array", "items": {"type": "string"}},
            "experience_years": {"type": "integer", "minimum": 0, "maximum": 60},
            "education": {"type": "string"},
            "projects": {"type": "array", "items": {"type": "string"}},
            "links": {"type": "object", "additionalProperties": True},
            "preferences": {"type": "object", "additionalProperties": True},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["skills", "experience_years", "education", "projects", "links", "preferences", "warnings"],
    }

    geo_location = str(preferences.get("location") or preferences.get("country") or "").strip()

    input_payload = {
        "preferences_input": preferences,
        "existing_profile": existing_profile or {},
        "confirmed_attributes": confirmed_attributes or {},
        "document_text": text[:settings.OPENAI_PROFILE_MAX_INPUT_CHARS],
        "constraints": {"geo": geo_location} if geo_location else {},
    }

    location_instruction = f"Merge preferences_input into preferences, and normalize location to {geo_location}." if geo_location else "Merge preferences_input into preferences."

    data = _openai_json(
        client=client,
        model=settings.OPENAI_MODEL,
        instructions=(
            "Extract an applicant profile from resume/cover-letter text.\n"
            "Only use facts present in the input. Do not invent.\n"
            "Return JSON matching the schema. Skills should be a deduped list.\n"
            "experience_years should be your best estimate as an integer.\n"
            "Extract a short list of notable past projects if present.\n"
            "Extract portfolio/github/linkedin links when present in the text OR provided via preferences_input.\n"
            f"{location_instruction}\n"
        ),
        input_text=json.dumps(input_payload, ensure_ascii=False),
        schema=schema,
        schema_name="user_profile_scour",
        temperature=0.2,
    )
    
    links: Dict[str, Any] = dict(data.get("links") or {})
    for k in ("portfolio_url", "github_url", "linkedin_url"):
        v = preferences.get(k)
        if isinstance(v, str) and v.strip() and k not in links:
            links[k] = v.strip()

    profile = UserProfileForScouring(
        skills=[s for s in (data.get("skills") or []) if isinstance(s, str) and s.strip()],
        experience_years=int(data.get("experience_years") or 0),
        education=str(data.get("education") or ""),
        projects=[p for p in (data.get("projects") or []) if isinstance(p, str) and p.strip()][:20],
        links=links,
        preferences=dict(data.get("preferences") or {}),
    )
    return profile


# ─── Job Scoring ─────────────────────────────────────────────

def score_jobs_with_embeddings(
    *,
    user_profile: UserProfileForScouring,
    jobs: List[Dict[str, Any]],
    relevance_threshold: int = 60,
) -> List[Dict[str, Any]]:
    """
    Computes a relevance_index using OpenAI embeddings and filters below threshold.
    """
    if not jobs:
        return []

    try:
        client = _openai_client()
    except Exception:
        for j in jobs:
            j["relevance_index"] = int(j.get("relevance_index") or 0)
        return jobs

    profile_text = json.dumps(user_profile.model_dump(), ensure_ascii=False)
    job_texts = []
    for j in jobs:
        job_texts.append(
            "\n".join([
                str(j.get("title") or ""),
                str(j.get("company") or ""),
                str(j.get("location") or ""),
                str(j.get("description") or ""),
                str(j.get("requirements") or ""),
            ])[:4000]
        )

    try:
        profile_emb = client.embeddings.create(model="text-embedding-3-small", input=[profile_text]).data[0].embedding
        job_embs = client.embeddings.create(model="text-embedding-3-small", input=job_texts).data
    except Exception:
        for j in jobs:
            j["relevance_index"] = int(j.get("relevance_index") or 0)
        return jobs

    scored: List[Dict[str, Any]] = []
    for j, emb in zip(jobs, job_embs):
        sim = _cosine_similarity(profile_emb, emb.embedding)
        score = _relevance_from_cos(sim)
        j["relevance_index"] = score
        if score >= relevance_threshold:
            scored.append(j)
    return scored


# ─── Job Enrichment ──────────────────────────────────────────

def enrich_jobs_with_openai(
    *,
    user_profile: UserProfileForScouring,
    preferences: Dict[str, Any],
    jobs: List[Dict[str, Any]],
    batch_size: int = 25,
    location: str = "",
) -> List[ScouredJob]:
    """
    Adds difficulty/competitiveness/rationale/tips via GPT in batches.
    """
    if not jobs:
        return []

    settings = get_settings()
    client = _openai_client()

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "jobs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "title": {"type": "string"},
                        "company": {"type": "string"},
                        "location": {"type": "string"},
                        "salary_range": {"type": "string"},
                        "posted_date": {"type": "string"},
                        "url": {"type": "string"},
                        "source_domain": {"type": "string"},
                        "description": {"type": "string"},
                        "requirements": {"type": "string"},
                        "relevance_index": {"type": "integer", "minimum": 0, "maximum": 100},
                        "difficulty": {"type": "string", "enum": ["low", "medium", "high"]},
                        "competitiveness": {"type": "string", "enum": ["low", "medium", "high"]},
                        "rationale": {"type": "string"},
                        "application_tips": {"type": "string"},
                    },
                },
            },
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["jobs", "warnings"],
    }

    effective_location = location or str(preferences.get("location") or "").strip()
    applicant_context = f"a {effective_location} applicant" if effective_location else "an applicant"

    out: List[ScouredJob] = []
    for i in range(0, len(jobs), batch_size):
        batch = jobs[i:i + batch_size]
        data = _openai_json(
            client=client,
            model=settings.OPENAI_MODEL,
            instructions=(
                f"You rank and explain job openings for {applicant_context}.\n"
                "CRITICAL: Return ALL provided jobs with enrichment. Do NOT filter any jobs out.\n"
                "For each job, add:\n"
                " - relevance_index (0-100 based on skill match)\n"
                " - difficulty (low/medium/high based on requirements)\n"
                " - competitiveness (low/medium/high based on company prestige)\n"
                " - rationale (why this job suits the applicant)\n"
                " - application_tips (actionable advice)\n"
                "Return JSON matching the schema. Include ALL jobs from the input.\n"
            ),
            input_text=json.dumps({
                "user_profile": user_profile.model_dump(),
                "preferences": preferences,
                "jobs": batch,
            }, ensure_ascii=False),
            schema=schema,
            schema_name="job_enrichment",
            temperature=0.2,
        )

        jobs_data = data.get("jobs") or []
        for j in jobs_data:
            try:
                j.setdefault("relevance_index", 50)
                j.setdefault("rationale", "")
                j.setdefault("application_tips", "")
                j.setdefault("description", "")
                j.setdefault("requirements", "")
                j.setdefault("source_domain", "")

                # Normalize difficulty
                difficulty_raw = str(j.get("difficulty", "medium")).lower()
                if difficulty_raw in ("low", "easy"):
                    j["difficulty"] = "low"
                elif difficulty_raw in ("high", "hard", "difficult"):
                    j["difficulty"] = "high"
                else:
                    j["difficulty"] = "medium"

                # Normalize competitiveness
                comp_raw = str(j.get("competitiveness", "medium")).lower()
                if "low" in comp_raw:
                    j["competitiveness"] = "low"
                elif "high" in comp_raw:
                    j["competitiveness"] = "high"
                else:
                    j["competitiveness"] = "medium"

                # Extract source_domain from URL if missing
                if not j.get("source_domain") and j.get("url"):
                    from urllib.parse import urlparse
                    try:
                        parsed = urlparse(j["url"])
                        j["source_domain"] = parsed.netloc.replace("www.", "")
                    except:
                        j["source_domain"] = ""

                job = ScouredJob(**j)
                out.append(job)
            except Exception as e:
                logger.warning(f"Failed to parse job: {e}")
                continue

    return out


# ─── Job Filtering ───────────────────────────────────────────

_CURRENCY_NUMBER_RE = re.compile(
    r"(?:[$£€¥₹]|[A-Z]{3})\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)"
)


def _parse_salary_numbers(text: str) -> List[int]:
    """Extract numeric salary values from text."""
    if not text:
        return []
    nums: List[int] = []
    for m in _CURRENCY_NUMBER_RE.finditer(text):
        raw = m.group(1).replace(",", "")
        try:
            nums.append(int(raw))
        except ValueError:
            continue
    return nums


def filter_jobs_by_preferences(*, preferences: Dict[str, Any], jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter jobs by user preferences.
    - salary_min: drops jobs with parsed max salary < min
    - remote: drops jobs that explicitly say onsite when remote is required
    - include_keywords: keeps jobs matching at least one keyword
    - exclude_keywords: drops jobs matching any keyword
    """
    if not jobs:
        return []

    salary_min = preferences.get("salary_min") or preferences.get("salary_min_gbp")
    try:
        salary_min = int(salary_min) if salary_min is not None else None
    except Exception:
        salary_min = None

    remote_required = preferences.get("remote") is True

    include_keywords = preferences.get("include_keywords") or []
    exclude_keywords = preferences.get("exclude_keywords") or []
    if isinstance(include_keywords, str):
        include_keywords = [s.strip() for s in include_keywords.split(",") if s.strip()]
    if isinstance(exclude_keywords, str):
        exclude_keywords = [s.strip() for s in exclude_keywords.split(",") if s.strip()]
    if not isinstance(include_keywords, list):
        include_keywords = []
    if not isinstance(exclude_keywords, list):
        exclude_keywords = []
    include_kw = [str(s).lower() for s in include_keywords if str(s).strip()]
    exclude_kw = [str(s).lower() for s in exclude_keywords if str(s).strip()]

    out: List[Dict[str, Any]] = []
    for j in jobs:
        hay = " ".join([str(j.get("title") or ""), str(j.get("description") or "")]).lower()
        if exclude_kw and any(k in hay for k in exclude_kw):
            continue
        if include_kw and not any(k in hay for k in include_kw):
            continue

        if salary_min is not None:
            nums = _parse_salary_numbers(str(j.get("salary_range") or ""))
            if nums and max(nums) < salary_min:
                continue

        if remote_required:
            loc = (j.get("location") or "").lower()
            desc = (j.get("description") or "").lower()
            if ("on-site" in loc or "onsite" in loc) and "remote" not in loc:
                continue
            if ("on-site" in desc or "onsite" in desc) and "remote" not in desc:
                continue

        out.append(j)

    return out
