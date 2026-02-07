"""
Job Scourer — Core job board scraping logic for CV Magic.

Searches whitelisted job boards, extracts job listings,
and returns normalized job data.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import quote_plus, urlparse

from .models import UserProfileForScouring

logger = logging.getLogger(__name__)


# ─── Domain Whitelist ────────────────────────────────────────

WHITELISTED_DOMAINS: Tuple[str, ...] = (
    "linkedin.com",
    "indeed.co.uk",
    "indeed.com",
    "glassdoor.co.uk",
    "glassdoor.com",
    "monster.co.uk",
    "monster.com",
    "reed.co.uk",
    "cv-library.co.uk",
    "totaljobs.com",
)


@dataclass(frozen=True)
class WhitelistCheck:
    allowed: bool
    domain: str


def _host_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().split("@")[-1]
    if ":" in host:
        host = host.split(":", 1)[0]
    return host


def _is_subdomain(host: str, domain: str) -> bool:
    host = host.lower().strip(".")
    domain = domain.lower().strip(".")
    return host == domain or host.endswith("." + domain)


def is_url_whitelisted(url: str, allowed_domains: Iterable[str] = WHITELISTED_DOMAINS) -> WhitelistCheck:
    host = _host_from_url(url)
    for domain in allowed_domains:
        if _is_subdomain(host, domain):
            return WhitelistCheck(True, domain)
    return WhitelistCheck(False, host)


# ─── Text Utilities ──────────────────────────────────────────

def _norm_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_tags(text: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", text or "")).strip()


# ─── Search URL Builders ─────────────────────────────────────

def _build_search_terms(*, user_profile: UserProfileForScouring, preferences: Dict[str, Any]) -> str:
    job_title = _norm_space(str(preferences.get("job_title") or "")) or "jobs"

    include_keywords = preferences.get("include_keywords") or preferences.get("keywords") or []
    if isinstance(include_keywords, str):
        include_keywords = [k.strip() for k in include_keywords.split(",") if k.strip()]
    if not isinstance(include_keywords, list):
        include_keywords = []

    seniority = _norm_space(str(preferences.get("seniority") or ""))
    if not seniority:
        y = int(getattr(user_profile, "experience_years", 0) or 0)
        if y >= 7:
            seniority = "senior"
        elif y <= 2:
            seniority = "junior"

    remote_required = preferences.get("remote") is True
    employment_type = _norm_space(str(preferences.get("employment_type") or ""))
    visa_required = preferences.get("visa_sponsorship_required") is True

    skills = getattr(user_profile, "skills", []) or []
    projects = getattr(user_profile, "projects", []) or []

    parts: List[str] = [job_title]
    if seniority:
        parts.append(seniority)
    if remote_required:
        parts.append("remote")
    if employment_type:
        parts.append(employment_type)
    if visa_required:
        parts.append("visa sponsorship")

    for s in skills[:4]:
        s = _norm_space(str(s))
        if s and s.lower() not in job_title.lower():
            parts.append(s)
    for p in projects[:2]:
        p = _norm_space(str(p))
        if p:
            parts.append(p)
    for k in include_keywords[:4]:
        k = _norm_space(str(k))
        if k:
            parts.append(k)

    out = _norm_space(" ".join(parts))
    return out[:160]


def build_default_job_board_search_urls(
    *,
    user_profile: UserProfileForScouring,
    preferences: Dict[str, Any],
    allowed_domains: Tuple[str, ...] = WHITELISTED_DOMAINS,
) -> List[str]:
    """Build search URLs for whitelisted job boards."""
    location = _norm_space(str(preferences.get("location") or ""))
    q = _build_search_terms(user_profile=user_profile, preferences=preferences)
    location_slug = re.sub(r"[^a-z0-9]+", "-", location.lower()).strip("-") if location else ""

    urls: List[str] = []
    for d in allowed_domains:
        d = (d or "").strip().lower()
        if not d:
            continue

        if "indeed.co.uk" in d:
            urls.append(f"https://www.indeed.co.uk/jobs?q={quote_plus(q)}&l={quote_plus(location)}")
        elif "indeed.com" in d:
            urls.append(f"https://www.indeed.com/jobs?q={quote_plus(q)}&l={quote_plus(location)}")
        elif "reed.co.uk" in d:
            urls.append(f"https://www.reed.co.uk/jobs/jobs-in-{location_slug}?keywords={quote_plus(q)}")
        elif "cv-library.co.uk" in d:
            urls.append(f"https://www.cv-library.co.uk/search-jobs?keywords={quote_plus(q)}&location={quote_plus(location)}")
        elif "totaljobs.com" in d:
            urls.append(f"https://www.totaljobs.com/jobs?Keywords={quote_plus(q)}&Location={quote_plus(location)}")
        elif "monster.co.uk" in d:
            urls.append(f"https://www.monster.co.uk/jobs/search/?q={quote_plus(q)}&where={quote_plus(location)}")
        elif "monster.com" in d:
            urls.append(f"https://www.monster.com/jobs/search/?q={quote_plus(q)}&where={quote_plus(location)}")
        elif "glassdoor.co.uk" in d:
            urls.append(f"https://www.glassdoor.co.uk/Job/jobs.htm?sc.keyword={quote_plus(q)}")
        elif "glassdoor.com" in d:
            urls.append(f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={quote_plus(q)}")
        elif "linkedin.com" in d:
            urls.append(f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(q)}&location={quote_plus(location)}")

    # Filter to whitelisted URLs
    out: List[str] = []
    for u in urls:
        if is_url_whitelisted(u, allowed_domains).allowed:
            out.append(u)
    return out


# ─── JSON-LD Extraction ──────────────────────────────────────

def _parse_jobposting_objects(obj: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        t = obj.get("@type") or obj.get("type")
        if isinstance(t, str) and t.lower() == "jobposting":
            out.append(obj)
        for k in ("@graph", "graph", "mainEntity", "mainEntityOfPage"):
            if k in obj:
                out.extend(_parse_jobposting_objects(obj[k]))
        for v in obj.values():
            if isinstance(v, (dict, list)):
                out.extend(_parse_jobposting_objects(v))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_parse_jobposting_objects(item))
    return out


def _extract_job_from_jsonld(job: Dict[str, Any], fallback_url: str) -> Dict[str, Any]:
    title = _norm_space(str(job.get("title") or job.get("name") or ""))
    desc = _strip_tags(str(job.get("description") or ""))

    org = job.get("hiringOrganization") or {}
    if isinstance(org, list) and org:
        org = org[0]
    company = ""
    if isinstance(org, dict):
        company = _norm_space(str(org.get("name") or ""))

    job_loc = job.get("jobLocation") or job.get("joblocation") or {}
    if isinstance(job_loc, list) and job_loc:
        job_loc = job_loc[0]
    location = ""
    if isinstance(job_loc, dict):
        addr = job_loc.get("address") or {}
        if isinstance(addr, dict):
            parts = []
            for key in ("addressLocality", "addressRegion", "addressCountry"):
                v = addr.get(key)
                if v:
                    parts.append(str(v))
            location = _norm_space(", ".join(parts))

    url = str(job.get("url") or fallback_url or "")

    salary_range = ""
    base_salary = job.get("baseSalary") or {}
    if isinstance(base_salary, dict):
        cur = base_salary.get("currency") or base_salary.get("salaryCurrency") or ""
        val = base_salary.get("value") or {}
        if isinstance(val, dict):
            minv = val.get("minValue") or val.get("value") or ""
            maxv = val.get("maxValue") or ""
            unit = val.get("unitText") or ""
            if minv and maxv:
                salary_range = f"{cur} {minv}-{maxv} {unit}".strip()
            elif minv:
                salary_range = f"{cur} {minv} {unit}".strip()

    posted_date = _norm_space(str(job.get("datePosted") or ""))

    requirements = ""
    for k in ("qualifications", "skills", "experienceRequirements", "educationRequirements"):
        v = job.get(k)
        if not v:
            continue
        if isinstance(v, list):
            requirements = _norm_space("; ".join([_strip_tags(str(x)) for x in v if str(x).strip()]))
        else:
            requirements = _norm_space(_strip_tags(str(v)))
        if requirements:
            break

    source_domain = ""
    try:
        check = is_url_whitelisted(url)
        if check.allowed:
            source_domain = check.domain
    except Exception:
        source_domain = ""

    return {
        "title": title,
        "company": company,
        "location": location,
        "salary_range": salary_range,
        "posted_date": posted_date,
        "url": url,
        "source_domain": source_domain,
        "description": desc[:4000],
        "requirements": requirements[:2000],
    }


def extract_jobs_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract job listings from a parsed HTML payload."""
    url = str(payload.get("url") or "")
    jobs: List[Dict[str, Any]] = []
    for raw in payload.get("json_ld") or []:
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for jp in _parse_jobposting_objects(data):
            try:
                jobs.append(_extract_job_from_jsonld(jp, fallback_url=url))
            except Exception:
                continue
    return jobs


# ─── Validation ──────────────────────────────────────────────

def validate_and_normalize_jobs(
    *,
    jobs: List[Dict[str, Any]],
    allowed_domains: Tuple[str, ...] = WHITELISTED_DOMAINS,
    enforce_location: str = "",
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Validate and normalize extracted jobs."""
    warnings: List[str] = []
    out: List[Dict[str, Any]] = []
    seen_urls: Set[str] = set()

    for j in jobs or []:
        if not isinstance(j, dict):
            continue
        url = str(j.get("url") or "").strip()
        if not url:
            continue

        if allowed_domains:
            check = is_url_whitelisted(url, allowed_domains)
            if not check.allowed:
                continue

        title = _norm_space(str(j.get("title") or ""))
        if not title:
            continue

        location = _norm_space(str(j.get("location") or ""))
        if not location:
            warnings.append(f"Missing location for: {url}")

        if url in seen_urls:
            continue
        seen_urls.add(url)

        src_domain = str(j.get("source_domain") or "")
        if not src_domain and allowed_domains:
            try:
                chk = is_url_whitelisted(url, allowed_domains)
                src_domain = chk.domain if chk.allowed else ""
            except Exception:
                pass
        if not src_domain:
            try:
                src_domain = urlparse(url).netloc.replace("www.", "")
            except Exception:
                src_domain = ""

        out.append({
            "title": title[:200],
            "company": _norm_space(str(j.get("company") or ""))[:200],
            "location": location[:200],
            "salary_range": _norm_space(str(j.get("salary_range") or ""))[:200],
            "posted_date": _norm_space(str(j.get("posted_date") or ""))[:100],
            "url": url,
            "source_domain": src_domain,
            "description": _norm_space(str(j.get("description") or ""))[:6000],
            "requirements": _norm_space(str(j.get("requirements") or ""))[:4000],
        })

    return out, warnings


# ─── URL Detection ───────────────────────────────────────────

_PAGINATION_RE = re.compile(r"([?&](page|p|start|fromage|offset)=[0-9]+)", re.IGNORECASE)
_JOB_URL_HINT_RE = re.compile(
    r"(/viewjob|/jobs/view|/job/|/job\\?|/position/|/vacancy/|/jobs/[^/]+/\\d{4,})",
    re.IGNORECASE,
)


def _is_pagination_url(url: str) -> bool:
    return bool(_PAGINATION_RE.search(url or ""))


def _is_job_detail_url(url: str, allowed_domains: Iterable[str]) -> bool:
    check = is_url_whitelisted(url, allowed_domains)
    if not check.allowed:
        return False
    path = (urlparse(url).path or "").lower()
    if not path or path in {"/", "/jobs", "/jobs/"}:
        return False
    if any(bad in path for bad in ("/jobs/jobs-in-", "/job/jobs.htm", "/jobs/search", "/search-jobs")):
        return False
    if any(x in path for x in ("/signin", "/login", "/register", "/companies", "/salary", "/help")):
        return False
    if _JOB_URL_HINT_RE.search(path):
        return True
    q = (urlparse(url).query or "").lower()
    if "jk=" in q or "jobid=" in q or "vacancyreference=" in q:
        return True
    return False


# ─── Main Scouring Function ──────────────────────────────────

def scour_jobs_with_brightdata(
    *,
    user_profile: UserProfileForScouring,
    preferences: Dict[str, Any],
    search_urls: List[str],
    target_openings: int,
    allowed_domains: Tuple[str, ...] = WHITELISTED_DOMAINS,
    max_listing_pages: int = 30,
    max_job_pages: int = 220,
    timeout_s: int = 35,
    max_bytes: int = 900_000,
    text_excerpt_chars: int = 12_000,
    fetch_mode: str = "auto",
    country: str = "",
    enforce_location: str = "",
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Scour job boards using BrightData proxy.
    
    1. Fetches job-board search/listing pages
    2. Extracts job detail URLs + pagination
    3. Fetches job detail pages and extracts JSON-LD JobPosting
    4. Validates/normalizes outputs
    """
    warnings: List[str] = []
    search_urls = [u for u in (search_urls or []) if isinstance(u, str) and u.strip()]
    if not search_urls:
        warnings.append("No search URLs provided.")
        return [], warnings

    try:
        from .brightdata_http import brightdata_get
        from .brightdata_agent_tools import parse_html_payload
    except ImportError as e:
        warnings.append(f"BrightData services not available: {e}")
        return [], warnings

    # Simplified HTTP-only fetch for now
    def fetch_payload(url: str) -> Dict[str, Any]:
        resp = brightdata_get(url=url, timeout_s=timeout_s, max_bytes=max_bytes, country=country or None)
        return parse_html_payload(
            url=resp.url,
            html=resp.text or "",
            status_code=resp.status_code,
            content_type=resp.content_type,
            text_excerpt_chars=text_excerpt_chars,
        )

    # Phase 1: crawl listing pages to gather job URLs
    listing_q: Deque[str] = deque(search_urls[:min(20, len(search_urls))])
    visited_listing: Set[str] = set()
    job_urls: Set[str] = set()

    listing_fetches = 0
    while listing_q and listing_fetches < max_listing_pages and len(job_urls) < max_job_pages:
        u = listing_q.popleft()
        if u in visited_listing:
            continue
        visited_listing.add(u)
        listing_fetches += 1

        try:
            payload = fetch_payload(u)
        except Exception as e:
            warnings.append(f"Failed to fetch listing page: {u} ({type(e).__name__}: {e})")
            continue

        links = payload.get("links") or []
        added_pages = 0
        for link in links:
            if not isinstance(link, str) or not link:
                continue
            if _is_job_detail_url(link, allowed_domains):
                job_urls.add(link)
            elif _is_pagination_url(link) and link not in visited_listing:
                if is_url_whitelisted(link, allowed_domains).allowed:
                    if added_pages < 5 and (len(visited_listing) + len(listing_q)) < max_listing_pages:
                        listing_q.append(link)
                        added_pages += 1

        if listing_fetches % 5 == 0:
            logger.info("Listing fetches=%s job_urls=%s", listing_fetches, len(job_urls))

    if not job_urls:
        warnings.append("No job URLs discovered from listing pages.")
        return [], warnings

    # Phase 2: fetch job detail pages and extract JSON-LD
    raw_jobs: List[Dict[str, Any]] = []
    job_fetches = 0
    started = time.time()

    for job_url in list(job_urls)[:max_job_pages]:
        job_fetches += 1
        try:
            payload = fetch_payload(job_url)
        except Exception as e:
            warnings.append(f"Failed to fetch job page: {job_url} ({type(e).__name__}: {e})")
            continue

        extracted = extract_jobs_from_payload(payload)
        if extracted:
            raw_jobs.extend(extracted)
        else:
            raw_jobs.append({
                "title": str(payload.get("title") or "").strip(),
                "company": "",
                "location": "",
                "salary_range": "",
                "posted_date": "",
                "url": str(payload.get("url") or job_url),
                "source_domain": "",
                "description": str(payload.get("text_excerpt") or "")[:4000],
                "requirements": "",
            })

        if len(raw_jobs) >= int(target_openings) * 3:
            break

    normalized, vwarn = validate_and_normalize_jobs(
        jobs=raw_jobs,
        allowed_domains=allowed_domains,
        enforce_location=enforce_location
    )
    warnings.extend(vwarn)

    if not normalized:
        warnings.append("No valid jobs extracted after validation.")

    elapsed = time.time() - started
    warnings.append(f"Scour stats: listing_pages={len(visited_listing)} job_urls={len(job_urls)} job_fetches={job_fetches} elapsed_s={elapsed:.1f}")

    return normalized, warnings
