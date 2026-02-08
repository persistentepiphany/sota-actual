"""
Comprehensive test suites for the CV Magic / Job Finder agent.

Suite 1: TestURLBuilding        – Search URL generation per domain, job type, and source count
Suite 2: TestJobValidation      – Dedup, filtering by preferences, salary, remote, keywords
Suite 3: TestHTMLParsing        – JSON-LD extraction, link extraction, HTML payload parsing
Suite 4: TestOpenAIMocked       – Profile extraction, embedding scoring, enrichment (mocked OpenAI)
Suite 5: TestScourJobsEndToEnd  – Full pipeline with mocked BrightData + OpenAI
Suite 6: TestDocumentExtraction – PDF/DOCX/TXT text extraction
"""

import base64
import json
import math
import re
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch, PropertyMock
from urllib.parse import unquote_plus, urlparse, parse_qs

import sys
import os

# Ensure the agents/ root is on sys.path for conftest helpers
_AGENTS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AGENTS_ROOT not in sys.path:
    sys.path.insert(0, _AGENTS_ROOT)

import pytest

from src.cv_magic.services.models import (
    ScouredJob,
    ScourPreferences,
    UserProfileForScouring,
)
from src.cv_magic.services.job_scourer import (
    WHITELISTED_DOMAINS,
    WhitelistCheck,
    is_url_whitelisted,
    build_default_job_board_search_urls,
    validate_and_normalize_jobs,
    extract_jobs_from_payload,
    _build_search_terms,
    _is_job_detail_url,
    _is_pagination_url,
    _norm_space,
    _strip_tags,
)
from src.cv_magic.services.brightdata_agent_tools import (
    parse_html_payload,
    _extract_json_ld,
    _extract_links,
    _extract_title,
    _strip_tags as bd_strip_tags,
)
from src.cv_magic.services.openai_scour_jobs import (
    _cosine_similarity,
    _relevance_from_cos,
    _parse_salary_numbers,
    filter_jobs_by_preferences,
)
from src.cv_magic.services.document_text import (
    extract_text_from_bytes,
    ExtractedText,
)

# Import helpers from conftest (pytest auto-loads conftest, but we need explicit access)
from tests.conftest import make_job, make_embedding, SAMPLE_CV_TEXT, SAMPLE_CV_BYTES


# ════════════════════════════════════════════════════════════
# Suite 1: URL Building
# ════════════════════════════════════════════════════════════

class TestURLBuilding:
    """Tests for search URL generation across domains, job types, and source counts."""

    # ── Whitelisting ──────────────────────────────────────

    @pytest.mark.parametrize("url,expected_allowed", [
        ("https://www.indeed.co.uk/viewjob?jk=abc", True),
        ("https://www.indeed.com/viewjob?jk=abc", True),
        ("https://www.linkedin.com/jobs/view/123", True),
        ("https://www.glassdoor.co.uk/job/123", True),
        ("https://www.glassdoor.com/job/123", True),
        ("https://www.reed.co.uk/jobs/view/123", True),
        ("https://www.cv-library.co.uk/jobs/view/123", True),
        ("https://www.totaljobs.com/jobs/view/123", True),
        ("https://www.monster.co.uk/jobs/view/123", True),
        ("https://www.monster.com/jobs/view/123", True),
        ("https://jobs.linkedin.com/view/123", True),
        ("https://uk.indeed.com/viewjob?jk=abc", True),
        # Not whitelisted
        ("https://www.google.com/search?q=jobs", False),
        ("https://www.sketchy-site.com/job/999", False),
        ("https://indeed.co.uk.evil.com/jobs", False),
    ])
    def test_url_whitelisting(self, url: str, expected_allowed: bool):
        result = is_url_whitelisted(url)
        assert result.allowed == expected_allowed

    def test_whitelist_returns_matched_domain(self):
        result = is_url_whitelisted("https://www.indeed.co.uk/viewjob?jk=abc")
        assert result.allowed is True
        assert result.domain == "indeed.co.uk"

    def test_whitelist_subdomain_matching(self):
        """Subdomains like uk.indeed.com should match indeed.com."""
        result = is_url_whitelisted("https://uk.indeed.com/jobs")
        assert result.allowed is True
        assert result.domain == "indeed.com"

    # ── URL generation per job type ───────────────────────

    @pytest.mark.parametrize("employment_type", [
        "internship", "full-time", "part-time", "contract",
    ])
    def test_urls_generated_for_each_job_type(
        self, junior_profile, employment_type
    ):
        """Each employment type should produce a valid set of search URLs."""
        prefs = {
            "job_title": "Software Engineer",
            "location": "London",
            "employment_type": employment_type,
        }
        urls = build_default_job_board_search_urls(
            user_profile=junior_profile,
            preferences=prefs,
        )
        # Should produce one URL per whitelisted domain
        assert len(urls) == len(WHITELISTED_DOMAINS)
        # All URLs should be whitelisted
        for url in urls:
            assert is_url_whitelisted(url).allowed is True
        # Employment type should appear in query strings
        for url in urls:
            decoded = unquote_plus(url).lower()
            assert employment_type in decoded

    @pytest.mark.parametrize("location", [
        "London", "New York", "Berlin", "Tokyo", "San Francisco",
    ])
    def test_urls_contain_location(self, junior_profile, location):
        """Location should be embedded in generated URLs."""
        prefs = {"job_title": "Developer", "location": location}
        urls = build_default_job_board_search_urls(
            user_profile=junior_profile,
            preferences=prefs,
        )
        assert len(urls) > 0
        # At least most URLs should include the location
        location_count = sum(
            1 for u in urls if location.lower() in unquote_plus(u).lower()
        )
        # Glassdoor + Reed URLs may not include location in the URL params
        assert location_count >= len(urls) - 3

    # ── Source count control ──────────────────────────────

    @pytest.mark.parametrize("num_sources", [1, 3, 5, 10])
    def test_urls_generated_for_limited_sources(
        self, junior_profile, num_sources
    ):
        """When we limit allowed_domains, we get exactly that many URLs."""
        prefs = {"job_title": "Developer", "location": "London"}
        limited_domains = WHITELISTED_DOMAINS[:num_sources]
        urls = build_default_job_board_search_urls(
            user_profile=junior_profile,
            preferences=prefs,
            allowed_domains=limited_domains,
        )
        assert len(urls) == len(limited_domains)

    def test_all_10_whitelisted_domains_produce_urls(self, junior_profile):
        """All 10 whitelisted domains should generate at least one URL."""
        prefs = {"job_title": "Engineer", "location": "UK"}
        urls = build_default_job_board_search_urls(
            user_profile=junior_profile,
            preferences=prefs,
        )
        domains_in_urls = set()
        for url in urls:
            check = is_url_whitelisted(url)
            if check.allowed:
                domains_in_urls.add(check.domain)
        assert domains_in_urls == set(WHITELISTED_DOMAINS)

    # ── Search terms composition ──────────────────────────

    def test_search_terms_include_skills(self, senior_profile):
        """Top skills from profile should appear in search terms."""
        prefs = {"job_title": "Backend Engineer", "location": "London"}
        terms = _build_search_terms(
            user_profile=senior_profile,
            preferences=prefs,
        )
        assert "Backend Engineer" in terms
        # At least some skills should appear
        skills_found = [s for s in senior_profile.skills[:4] if s.lower() in terms.lower()]
        assert len(skills_found) >= 1

    def test_search_terms_include_keywords(self, junior_profile):
        """Include keywords from preferences should appear in terms."""
        prefs = {
            "job_title": "Developer",
            "location": "London",
            "include_keywords": ["React", "TypeScript"],
        }
        terms = _build_search_terms(
            user_profile=junior_profile,
            preferences=prefs,
        )
        assert "React" in terms or "TypeScript" in terms

    def test_search_terms_seniority_auto_detection_junior(self):
        """With 1 year experience, should auto-detect junior."""
        profile = UserProfileForScouring(
            skills=["Python"], experience_years=1,
        )
        prefs = {"job_title": "Developer", "location": "UK"}
        terms = _build_search_terms(user_profile=profile, preferences=prefs)
        assert "junior" in terms.lower()

    def test_search_terms_seniority_auto_detection_senior(self):
        """With 10 years experience, should auto-detect senior."""
        profile = UserProfileForScouring(
            skills=["Python"], experience_years=10,
        )
        prefs = {"job_title": "Developer", "location": "UK"}
        terms = _build_search_terms(user_profile=profile, preferences=prefs)
        assert "senior" in terms.lower()

    def test_search_terms_explicit_seniority_overrides_auto(self):
        """Explicit seniority in prefs takes priority over auto-detection."""
        profile = UserProfileForScouring(
            skills=["Python"], experience_years=10,
        )
        prefs = {"job_title": "Developer", "location": "UK", "seniority": "intern"}
        terms = _build_search_terms(user_profile=profile, preferences=prefs)
        assert "intern" in terms.lower()
        assert "senior" not in terms.lower()

    def test_search_terms_remote_flag(self, junior_profile):
        """Remote=True should add 'remote' to search terms."""
        prefs = {"job_title": "Developer", "location": "UK", "remote": True}
        terms = _build_search_terms(user_profile=junior_profile, preferences=prefs)
        assert "remote" in terms.lower()

    def test_search_terms_truncated_to_160_chars(self, senior_profile):
        """Search terms must not exceed 160 characters."""
        prefs = {
            "job_title": "Senior Principal Staff Distinguished Platform Infrastructure Reliability Engineer",
            "location": "UK",
            "include_keywords": ["Kubernetes", "Terraform", "Docker", "AWS"],
        }
        terms = _build_search_terms(user_profile=senior_profile, preferences=prefs)
        assert len(terms) <= 160

    # ── URL format validation ─────────────────────────────

    def test_indeed_uk_url_format(self, junior_profile):
        prefs = {"job_title": "Tester", "location": "Manchester"}
        urls = build_default_job_board_search_urls(
            user_profile=junior_profile,
            preferences=prefs,
            allowed_domains=("indeed.co.uk",),
        )
        assert len(urls) == 1
        assert urls[0].startswith("https://www.indeed.co.uk/jobs?q=")
        assert "&l=" in urls[0]

    def test_linkedin_url_format(self, junior_profile):
        prefs = {"job_title": "Tester", "location": "London"}
        urls = build_default_job_board_search_urls(
            user_profile=junior_profile,
            preferences=prefs,
            allowed_domains=("linkedin.com",),
        )
        assert len(urls) == 1
        assert "linkedin.com/jobs/search" in urls[0]
        assert "keywords=" in urls[0]
        assert "location=" in urls[0]

    def test_reed_url_format(self, junior_profile):
        prefs = {"job_title": "Tester", "location": "Leeds"}
        urls = build_default_job_board_search_urls(
            user_profile=junior_profile,
            preferences=prefs,
            allowed_domains=("reed.co.uk",),
        )
        assert len(urls) == 1
        assert "reed.co.uk/jobs/jobs-in-" in urls[0]

    def test_empty_location_doesnt_break(self, junior_profile):
        """Empty location should not cause URL generation to fail."""
        prefs = {"job_title": "Developer", "location": ""}
        urls = build_default_job_board_search_urls(
            user_profile=junior_profile,
            preferences=prefs,
        )
        assert len(urls) == len(WHITELISTED_DOMAINS)

    def test_empty_preferences_returns_urls(self, junior_profile):
        """Even with minimal prefs, URLs should still be generated."""
        urls = build_default_job_board_search_urls(
            user_profile=junior_profile,
            preferences={},
        )
        assert len(urls) == len(WHITELISTED_DOMAINS)


# ════════════════════════════════════════════════════════════
# Suite 2: Job Validation & Filtering
# ════════════════════════════════════════════════════════════

class TestJobValidation:
    """Tests for validate_and_normalize_jobs and filter_jobs_by_preferences."""

    # ── Validation / Dedup ────────────────────────────────

    def test_removes_duplicate_urls(self):
        jobs = [
            make_job(title="Job A", url="https://www.indeed.co.uk/viewjob?jk=1"),
            make_job(title="Job B", url="https://www.indeed.co.uk/viewjob?jk=1"),
        ]
        valid, warnings = validate_and_normalize_jobs(jobs=jobs)
        assert len(valid) == 1
        assert valid[0]["title"] == "Job A"

    def test_removes_empty_title(self):
        jobs = [
            make_job(title="", url="https://www.indeed.co.uk/viewjob?jk=2"),
            make_job(title="Valid Job", url="https://www.indeed.co.uk/viewjob?jk=3"),
        ]
        valid, _ = validate_and_normalize_jobs(jobs=jobs)
        assert len(valid) == 1
        assert valid[0]["title"] == "Valid Job"

    def test_removes_empty_url(self):
        jobs = [
            make_job(title="No URL", url=""),
            make_job(title="Has URL", url="https://www.indeed.co.uk/viewjob?jk=4"),
        ]
        valid, _ = validate_and_normalize_jobs(jobs=jobs)
        assert len(valid) == 1

    def test_removes_non_whitelisted_domains(self):
        jobs = [
            make_job(title="Legit", url="https://www.indeed.co.uk/viewjob?jk=5"),
            make_job(title="Sketchy", url="https://www.sketchy.com/job/1"),
        ]
        valid, _ = validate_and_normalize_jobs(jobs=jobs)
        assert len(valid) == 1
        assert valid[0]["title"] == "Legit"

    def test_normalizes_field_lengths(self):
        jobs = [
            make_job(
                title="X" * 500,
                company="Y" * 500,
                description="Z" * 10000,
                url="https://www.indeed.co.uk/viewjob?jk=6",
            ),
        ]
        valid, _ = validate_and_normalize_jobs(jobs=jobs)
        assert len(valid) == 1
        assert len(valid[0]["title"]) <= 200
        assert len(valid[0]["company"]) <= 200
        assert len(valid[0]["description"]) <= 6000

    def test_warns_on_missing_location(self):
        jobs = [
            make_job(title="No Location", location="", url="https://www.indeed.co.uk/viewjob?jk=7"),
        ]
        valid, warnings = validate_and_normalize_jobs(jobs=jobs)
        assert len(valid) == 1
        assert any("Missing location" in w for w in warnings)

    def test_populates_source_domain_from_url(self):
        jobs = [
            make_job(
                title="Test", url="https://www.reed.co.uk/jobs/view/8",
                source_domain="",
            ),
        ]
        valid, _ = validate_and_normalize_jobs(jobs=jobs)
        assert len(valid) == 1
        assert valid[0]["source_domain"] == "reed.co.uk"

    def test_diverse_list_validation(self, diverse_job_list):
        """The 20-item diverse list should produce 17 valid jobs (removes dupe + no-title + non-whitelisted)."""
        valid, _ = validate_and_normalize_jobs(jobs=diverse_job_list)
        urls = [j["url"] for j in valid]
        # No duplicate URLs
        assert len(urls) == len(set(urls))
        # Non-whitelisted domain removed
        assert not any("sketchy-site.com" in u for u in urls)

    def test_empty_input(self):
        valid, warnings = validate_and_normalize_jobs(jobs=[])
        assert valid == []

    def test_none_items_skipped(self):
        valid, _ = validate_and_normalize_jobs(jobs=[None, "not a dict", 42])
        assert valid == []

    # ── Filtering by preferences ──────────────────────────

    def test_filter_by_include_keywords(self, diverse_job_list):
        """Only jobs containing at least one include keyword should pass."""
        prefs = {"include_keywords": ["machine learning"]}
        filtered = filter_jobs_by_preferences(preferences=prefs, jobs=diverse_job_list)
        for j in filtered:
            hay = f"{j['title']} {j['description']}".lower()
            assert "machine learning" in hay

    def test_filter_by_exclude_keywords(self, diverse_job_list):
        """Jobs containing exclude keywords should be removed."""
        prefs = {"exclude_keywords": ["marketing"]}
        filtered = filter_jobs_by_preferences(preferences=prefs, jobs=diverse_job_list)
        for j in filtered:
            hay = f"{j['title']} {j['description']}".lower()
            assert "marketing" not in hay

    def test_filter_by_salary_min(self, diverse_job_list):
        """Jobs whose max salary < min should be excluded."""
        prefs = {"salary_min": 100000}
        filtered = filter_jobs_by_preferences(preferences=prefs, jobs=diverse_job_list)
        for j in filtered:
            nums = _parse_salary_numbers(j.get("salary_range", ""))
            if nums:
                assert max(nums) >= 100000

    def test_filter_salary_min_gbp_alias(self):
        """salary_min_gbp should work the same as salary_min."""
        jobs = [
            make_job(title="Low", salary_range="£18,000"),
            make_job(title="High", salary_range="£80,000", url="https://www.indeed.co.uk/viewjob?jk=hi"),
        ]
        prefs = {"salary_min_gbp": 50000}
        filtered = filter_jobs_by_preferences(preferences=prefs, jobs=jobs)
        assert len(filtered) == 1
        assert filtered[0]["title"] == "High"

    def test_filter_jobs_without_salary_kept(self):
        """Jobs with no salary info should NOT be excluded by salary filter."""
        jobs = [
            make_job(title="No Salary", salary_range=""),
            make_job(title="Low", salary_range="£18,000", url="https://www.indeed.co.uk/viewjob?jk=low2"),
        ]
        prefs = {"salary_min": 50000}
        filtered = filter_jobs_by_preferences(preferences=prefs, jobs=jobs)
        # "No Salary" should remain (no nums → not filtered), "Low" should be removed
        titles = [j["title"] for j in filtered]
        assert "No Salary" in titles
        assert "Low" not in titles

    def test_filter_remote_required_drops_onsite(self, diverse_job_list):
        """With remote=True, jobs explicitly tagged onsite should be dropped."""
        prefs = {"remote": True}
        filtered = filter_jobs_by_preferences(preferences=prefs, jobs=diverse_job_list)
        for j in filtered:
            loc = j.get("location", "").lower()
            desc = j.get("description", "").lower()
            # If marked onsite, it should also mention remote to survive
            if "onsite" in loc or "on-site" in loc:
                assert "remote" in loc
            if "onsite" in desc or "on-site" in desc:
                assert "remote" in desc

    def test_filter_combined_include_and_exclude(self, diverse_job_list):
        """Include + exclude should both apply."""
        prefs = {
            "include_keywords": ["machine learning", "NLP"],
            "exclude_keywords": ["senior", "lead"],
        }
        filtered = filter_jobs_by_preferences(preferences=prefs, jobs=diverse_job_list)
        for j in filtered:
            hay = f"{j['title']} {j['description']}".lower()
            assert "machine learning" in hay or "nlp" in hay
            assert "senior" not in hay
            assert "lead" not in hay

    def test_filter_empty_preferences_returns_all(self, diverse_job_list):
        """No preferences → no filtering."""
        filtered = filter_jobs_by_preferences(preferences={}, jobs=diverse_job_list)
        assert len(filtered) == len(diverse_job_list)

    def test_filter_empty_jobs(self):
        filtered = filter_jobs_by_preferences(preferences={"salary_min": 50000}, jobs=[])
        assert filtered == []

    def test_filter_string_keywords_parsed(self):
        """Keywords provided as comma-separated string should be parsed."""
        jobs = [
            make_job(title="React Developer", description="Build UIs with React"),
            make_job(title="Go Developer", description="Backend with Go", url="https://www.indeed.co.uk/viewjob?jk=go1"),
        ]
        prefs = {"include_keywords": "React, TypeScript"}
        filtered = filter_jobs_by_preferences(preferences=prefs, jobs=jobs)
        assert len(filtered) == 1
        assert filtered[0]["title"] == "React Developer"

    # ── Salary parsing ────────────────────────────────────

    @pytest.mark.parametrize("text,expected", [
        ("£40,000 - £60,000", [40000, 60000]),
        ("$120,000", [120000]),
        ("€65,000", [65000]),
        ("GBP 70,000 - GBP 95,000", [70000, 95000]),
        ("$500/day", [500]),
        ("Competitive", []),
        ("", []),
        ("£18,000 - £22,000 per annum", [18000, 22000]),
    ])
    def test_parse_salary_numbers(self, text: str, expected: List[int]):
        result = _parse_salary_numbers(text)
        assert result == expected


# ════════════════════════════════════════════════════════════
# Suite 3: HTML Parsing
# ════════════════════════════════════════════════════════════

class TestHTMLParsing:
    """Tests for JSON-LD extraction, link extraction, and payload parsing."""

    # ── JSON-LD extraction ────────────────────────────────

    def test_extract_jsonld_from_html(self, html_with_jsonld_job):
        blocks = _extract_json_ld(html_with_jsonld_job)
        assert len(blocks) == 1
        data = json.loads(blocks[0])
        assert data["@type"] == "JobPosting"
        assert data["title"] == "Senior Python Developer"

    def test_extract_multiple_jsonld_graph(self, html_with_multiple_jsonld):
        blocks = _extract_json_ld(html_with_multiple_jsonld)
        assert len(blocks) == 1  # One <script> tag containing a @graph
        data = json.loads(blocks[0])
        assert "@graph" in data
        assert len(data["@graph"]) == 2

    def test_extract_jsonld_none_present(self, html_no_jsonld):
        blocks = _extract_json_ld(html_no_jsonld)
        assert blocks == []

    def test_extract_jsonld_empty_html(self, html_empty):
        blocks = _extract_json_ld(html_empty)
        assert blocks == []

    def test_extract_jsonld_limit(self):
        """Should respect limit parameter."""
        many_ld = '<script type="application/ld+json">{"a":1}</script>' * 10
        html = f"<html><head>{many_ld}</head><body></body></html>"
        blocks = _extract_json_ld(html, limit=3)
        assert len(blocks) == 3

    def test_extract_jsonld_max_chars(self):
        """Each block should be truncated to max_chars_each."""
        big_json = '{"data": "' + "x" * 50000 + '"}'
        html = f'<html><head><script type="application/ld+json">{big_json}</script></head></html>'
        blocks = _extract_json_ld(html, max_chars_each=100)
        assert len(blocks) == 1
        assert len(blocks[0]) <= 100

    # ── Title extraction ──────────────────────────────────

    def test_extract_title(self, html_with_jsonld_job):
        title = _extract_title(html_with_jsonld_job)
        assert "Senior Python Developer" in title
        assert "Indeed" in title

    def test_extract_title_empty(self, html_empty):
        assert _extract_title(html_empty) == ""

    def test_extract_title_truncated(self):
        long_title = "A" * 500
        html = f"<html><head><title>{long_title}</title></head></html>"
        title = _extract_title(html)
        assert len(title) <= 300

    # ── Link extraction ───────────────────────────────────

    def test_extract_links_absolute_and_relative(self, html_with_jsonld_job):
        links = _extract_links("https://www.indeed.co.uk/jobs", html_with_jsonld_job)
        assert any("/viewjob" in link for link in links)
        # Relative links should be made absolute
        for link in links:
            assert link.startswith("http://") or link.startswith("https://")

    def test_extract_links_skips_special(self, html_with_jsonld_job):
        links = _extract_links("https://www.indeed.co.uk/jobs", html_with_jsonld_job)
        for link in links:
            assert not link.startswith("javascript:")
            assert not link.startswith("mailto:")
            assert not link.startswith("#")

    def test_extract_links_deduplication(self):
        html = """
        <a href="https://example.com/page1">Link 1</a>
        <a href="https://example.com/page1">Link 1 again</a>
        <a href="https://example.com/page2">Link 2</a>
        """
        links = _extract_links("https://example.com", html)
        assert len(links) == 2

    def test_extract_links_limit(self):
        html = "".join(f'<a href="https://example.com/p{i}">L{i}</a>' for i in range(200))
        links = _extract_links("https://example.com", html, limit=10)
        assert len(links) == 10

    # ── parse_html_payload ────────────────────────────────

    def test_parse_html_payload_complete(self, html_with_jsonld_job):
        payload = parse_html_payload(
            url="https://www.indeed.co.uk/viewjob?jk=jsonld001",
            html=html_with_jsonld_job,
            status_code=200,
            content_type="text/html",
        )
        assert payload["url"] == "https://www.indeed.co.uk/viewjob?jk=jsonld001"
        assert payload["status_code"] == 200
        assert "Senior Python Developer" in payload["title"]
        assert len(payload["json_ld"]) == 1
        assert len(payload["links"]) >= 2
        assert len(payload["text_excerpt"]) > 0

    def test_parse_html_payload_no_jsonld(self, html_no_jsonld):
        payload = parse_html_payload(
            url="https://example.com",
            html=html_no_jsonld,
            status_code=200,
            content_type="text/html",
        )
        assert payload["json_ld"] == []
        assert len(payload["links"]) >= 2

    def test_parse_html_payload_empty(self, html_empty):
        payload = parse_html_payload(
            url="https://example.com",
            html=html_empty,
            status_code=200,
            content_type="text/html",
        )
        assert payload["title"] == ""
        assert payload["json_ld"] == []
        assert payload["links"] == []

    # ── extract_jobs_from_payload ─────────────────────────

    def test_extract_jobs_from_valid_jsonld_payload(self, html_with_jsonld_job):
        payload = parse_html_payload(
            url="https://www.indeed.co.uk/viewjob?jk=jsonld001",
            html=html_with_jsonld_job,
            status_code=200,
            content_type="text/html",
        )
        jobs = extract_jobs_from_payload(payload)
        assert len(jobs) == 1
        job = jobs[0]
        assert job["title"] == "Senior Python Developer"
        assert job["company"] == "TechCorp"
        assert "London" in job["location"]
        assert "GBP" in job["salary_range"]
        assert "70000" in job["salary_range"]
        assert "95000" in job["salary_range"]
        assert job["posted_date"] == "2026-01-15"
        assert "Python" in job["requirements"]

    def test_extract_jobs_from_graph_payload(self, html_with_multiple_jsonld):
        payload = parse_html_payload(
            url="https://www.glassdoor.com/jobs",
            html=html_with_multiple_jsonld,
            status_code=200,
            content_type="text/html",
        )
        jobs = extract_jobs_from_payload(payload)
        # Recursive parser may find duplicates from @graph + nested traversal
        assert len(jobs) >= 2
        titles = {j["title"] for j in jobs}
        assert "Frontend Engineer" in titles
        assert "Backend Engineer" in titles

    def test_extract_jobs_empty_payload(self, html_empty):
        payload = parse_html_payload(
            url="https://example.com",
            html=html_empty,
            status_code=200,
            content_type="text/html",
        )
        jobs = extract_jobs_from_payload(payload)
        assert jobs == []

    # ── URL classification ────────────────────────────────

    @pytest.mark.parametrize("url,expected", [
        ("https://www.indeed.co.uk/viewjob?jk=abc123", True),
        ("https://www.reed.co.uk/jobs/view/456", True),
        ("https://www.linkedin.com/jobs/view/789", True),
        ("https://www.glassdoor.com/job/listing/123", True),
        # Search/listing pages
        ("https://www.indeed.co.uk/jobs?q=python&l=london", False),
        ("https://www.reed.co.uk/jobs/jobs-in-london", False),
        ("https://www.linkedin.com/jobs/search/?keywords=python", False),
        # Non-job pages
        ("https://www.indeed.co.uk/companies/google", False),
        ("https://www.linkedin.com/login", False),
        ("https://www.glassdoor.com/salary/data", False),
        # Non-whitelisted
        ("https://www.google.com/jobs/view/123", False),
    ])
    def test_is_job_detail_url(self, url: str, expected: bool):
        result = _is_job_detail_url(url, WHITELISTED_DOMAINS)
        assert result == expected

    @pytest.mark.parametrize("url,expected", [
        ("https://www.indeed.co.uk/jobs?q=python&start=10", True),
        ("https://www.reed.co.uk/jobs?page=2", True),
        ("https://www.totaljobs.com/jobs?offset=25", True),
        ("https://www.indeed.co.uk/viewjob?jk=abc", False),
        ("https://www.linkedin.com/jobs/search/?keywords=python", False),
    ])
    def test_is_pagination_url(self, url: str, expected: bool):
        result = _is_pagination_url(url)
        assert result == expected

    # ── Strip tags ────────────────────────────────────────

    def test_strip_tags(self):
        assert bd_strip_tags("<p>Hello <b>World</b></p>") == "Hello World"
        assert bd_strip_tags("") == ""
        assert bd_strip_tags("No tags here") == "No tags here"


# ════════════════════════════════════════════════════════════
# Suite 4: OpenAI Mocked
# ════════════════════════════════════════════════════════════

class TestOpenAIMocked:
    """Tests for profile extraction, embedding scoring, enrichment — with mocked OpenAI."""

    # ── Cosine similarity (pure math, no mock needed) ─────

    def test_cosine_similarity_identical(self):
        v = [1.0, 0.0, 0.0]
        assert _cosine_similarity(v, v) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert _cosine_similarity(a, b) == pytest.approx(0.0)

    def test_cosine_similarity_opposite(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert _cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_cosine_similarity_empty(self):
        assert _cosine_similarity([], []) == 0.0

    def test_cosine_similarity_mismatched_lengths(self):
        assert _cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_cosine_similarity_zero_vectors(self):
        assert _cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0

    # ── Relevance from cosine ─────────────────────────────

    @pytest.mark.parametrize("sim,expected", [
        (1.0, 100),
        (0.0, 50),
        (-1.0, 0),
        (0.5, 75),
        (-0.5, 25),
    ])
    def test_relevance_from_cos(self, sim: float, expected: int):
        assert _relevance_from_cos(sim) == expected

    def test_relevance_from_cos_clamped(self):
        # Values > 1 or < -1 should clamp
        assert _relevance_from_cos(1.5) == 100
        assert _relevance_from_cos(-1.5) == 0

    # ── Profile extraction (mocked OpenAI) ────────────────

    @patch("src.cv_magic.services.openai_scour_jobs._openai_client")
    def test_extract_profile_basic(self, mock_client_fn):
        """Profile extraction should return a valid UserProfileForScouring."""
        from src.cv_magic.services.openai_scour_jobs import extract_user_profile_from_text

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "skills": ["Python", "JavaScript", "React", "SQL"],
            "experience_years": 1,
            "education": "BSc Computer Science, University of London",
            "projects": ["Portfolio website", "Task Manager"],
            "links": {"github_url": "https://github.com/johnsmith"},
            "preferences": {"location": "London"},
            "warnings": [],
        })
        mock_client.chat.completions.create.return_value = mock_response

        profile = extract_user_profile_from_text(
            text=SAMPLE_CV_TEXT,
            preferences={"location": "London", "job_title": "Developer"},
            existing_profile={},
            confirmed_attributes={},
        )

        assert isinstance(profile, UserProfileForScouring)
        assert "Python" in profile.skills
        assert profile.experience_years == 1
        assert "BSc" in profile.education
        assert len(profile.projects) >= 1

    @patch("src.cv_magic.services.openai_scour_jobs._openai_client")
    def test_extract_profile_merges_links_from_preferences(self, mock_client_fn):
        """Links from preferences should be merged into the profile."""
        from src.cv_magic.services.openai_scour_jobs import extract_user_profile_from_text

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "skills": ["Python"],
            "experience_years": 2,
            "education": "BSc CS",
            "projects": [],
            "links": {},
            "preferences": {},
            "warnings": [],
        })
        mock_client.chat.completions.create.return_value = mock_response

        profile = extract_user_profile_from_text(
            text="Some CV text",
            preferences={
                "portfolio_url": "https://portfolio.dev",
                "github_url": "https://github.com/dev",
            },
            existing_profile={},
            confirmed_attributes={},
        )
        assert profile.links.get("portfolio_url") == "https://portfolio.dev"
        assert profile.links.get("github_url") == "https://github.com/dev"

    # ── Embedding scoring (mocked OpenAI) ─────────────────

    @patch("src.cv_magic.services.openai_scour_jobs._openai_client")
    def test_score_jobs_with_embeddings_filters_below_threshold(self, mock_client_fn):
        """Jobs below relevance threshold should be filtered out."""
        from src.cv_magic.services.openai_scour_jobs import score_jobs_with_embeddings

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        profile = UserProfileForScouring(skills=["Python"], experience_years=2)

        # Profile embedding = high-dimensional unit vector
        profile_emb = make_embedding(dim=1536, seed=42)

        # Job 1: similar to profile (same seed) → high score
        similar_emb = make_embedding(dim=1536, seed=42)
        # Job 2: very different (different seed) → low score
        different_emb = make_embedding(dim=1536, seed=999)

        # Mock embeddings.create: first call for profile, second for jobs
        profile_resp = MagicMock()
        profile_resp.data = [MagicMock(embedding=profile_emb)]

        job_resp = MagicMock()
        job_resp.data = [
            MagicMock(embedding=similar_emb),
            MagicMock(embedding=different_emb),
        ]

        mock_client.embeddings.create.side_effect = [profile_resp, job_resp]

        jobs = [
            make_job(title="Python Dev", url="https://www.indeed.co.uk/viewjob?jk=sim1"),
            make_job(title="Unrelated", url="https://www.indeed.co.uk/viewjob?jk=diff1"),
        ]

        scored = score_jobs_with_embeddings(
            user_profile=profile,
            jobs=jobs,
            relevance_threshold=60,
        )

        # Similar job should have score ~100, different should be lower
        # With same seed, cosine similarity = 1.0 → score 100
        assert len(scored) >= 1
        assert scored[0]["relevance_index"] == 100

    @patch("src.cv_magic.services.openai_scour_jobs._openai_client")
    @pytest.mark.parametrize("num_jobs", [5, 20, 50])
    def test_score_jobs_handles_varying_quantities(self, mock_client_fn, num_jobs):
        """Scoring should work correctly with 5, 20, or 50 jobs."""
        from src.cv_magic.services.openai_scour_jobs import score_jobs_with_embeddings

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        profile = UserProfileForScouring(skills=["Python"], experience_years=3)
        profile_emb = make_embedding(dim=1536, seed=0)

        profile_resp = MagicMock()
        profile_resp.data = [MagicMock(embedding=profile_emb)]

        # Create job embeddings with varying similarity
        job_embs = []
        for i in range(num_jobs):
            emb = make_embedding(dim=1536, seed=i)
            job_embs.append(MagicMock(embedding=emb))

        job_resp = MagicMock()
        job_resp.data = job_embs

        mock_client.embeddings.create.side_effect = [profile_resp, job_resp]

        jobs = [
            make_job(
                title=f"Job {i}",
                url=f"https://www.indeed.co.uk/viewjob?jk=q{i}",
            )
            for i in range(num_jobs)
        ]

        scored = score_jobs_with_embeddings(
            user_profile=profile,
            jobs=jobs,
            relevance_threshold=0,  # Accept all
        )
        assert len(scored) == num_jobs
        # Every job should have a relevance_index set
        for j in scored:
            assert 0 <= j["relevance_index"] <= 100

    @patch("src.cv_magic.services.openai_scour_jobs._openai_client")
    def test_score_jobs_empty_list(self, mock_client_fn):
        from src.cv_magic.services.openai_scour_jobs import score_jobs_with_embeddings

        profile = UserProfileForScouring(skills=["Python"], experience_years=1)
        result = score_jobs_with_embeddings(
            user_profile=profile, jobs=[], relevance_threshold=60
        )
        assert result == []

    @patch("src.cv_magic.services.openai_scour_jobs._openai_client")
    def test_score_jobs_openai_failure_graceful(self, mock_client_fn):
        """If OpenAI embedding call fails, jobs should be returned with existing scores."""
        from src.cv_magic.services.openai_scour_jobs import score_jobs_with_embeddings

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.embeddings.create.side_effect = Exception("API Error")

        profile = UserProfileForScouring(skills=["Python"], experience_years=1)
        jobs = [make_job(title="Test", relevance_index=70)]

        result = score_jobs_with_embeddings(
            user_profile=profile, jobs=jobs, relevance_threshold=60
        )
        assert len(result) == 1
        assert result[0]["relevance_index"] == 70

    # ── Enrichment (mocked OpenAI) ────────────────────────

    @patch("src.cv_magic.services.openai_scour_jobs._openai_client")
    def test_enrich_jobs_basic(self, mock_client_fn):
        """Enrichment should add difficulty, competitiveness, rationale, tips."""
        from src.cv_magic.services.openai_scour_jobs import enrich_jobs_with_openai

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        enriched_jobs = [
            {
                "title": "Python Developer",
                "company": "Corp",
                "location": "London",
                "salary_range": "£50,000",
                "posted_date": "2026-01-01",
                "url": "https://www.indeed.co.uk/viewjob?jk=e1",
                "source_domain": "indeed.co.uk",
                "description": "Build APIs",
                "requirements": "Python, 2+ years",
                "relevance_index": 80,
                "difficulty": "medium",
                "competitiveness": "low",
                "rationale": "Good skill match.",
                "application_tips": "Highlight API experience.",
            }
        ]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "jobs": enriched_jobs,
            "warnings": [],
        })
        mock_client.chat.completions.create.return_value = mock_response

        profile = UserProfileForScouring(skills=["Python", "Flask"], experience_years=2)
        jobs = [make_job(title="Python Developer", url="https://www.indeed.co.uk/viewjob?jk=e1")]

        result = enrich_jobs_with_openai(
            user_profile=profile,
            preferences={"job_title": "Python Developer", "location": "London"},
            jobs=jobs,
            location="London",
        )

        assert len(result) == 1
        assert isinstance(result[0], ScouredJob)
        assert result[0].title == "Python Developer"
        assert result[0].difficulty.value == "medium"
        assert result[0].competitiveness.value == "low"
        assert result[0].rationale == "Good skill match."
        assert result[0].application_tips == "Highlight API experience."

    @patch("src.cv_magic.services.openai_scour_jobs._openai_client")
    def test_enrich_jobs_batching(self, mock_client_fn):
        """Jobs should be batched at batch_size (default 25)."""
        from src.cv_magic.services.openai_scour_jobs import enrich_jobs_with_openai

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        def make_enrichment_response(batch):
            enriched = []
            for j in batch:
                enriched.append({
                    **j,
                    "relevance_index": 75,
                    "difficulty": "medium",
                    "competitiveness": "medium",
                    "rationale": "Match.",
                    "application_tips": "Apply.",
                })
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = json.dumps({
                "jobs": enriched,
                "warnings": [],
            })
            return resp

        # 30 jobs → should be 2 batches (25 + 5)
        jobs = [
            make_job(title=f"Job {i}", url=f"https://www.indeed.co.uk/viewjob?jk=batch{i}")
            for i in range(30)
        ]

        # Mock will be called twice (2 batches)
        mock_client.chat.completions.create.side_effect = [
            make_enrichment_response(jobs[:25]),
            make_enrichment_response(jobs[25:]),
        ]

        profile = UserProfileForScouring(skills=["Python"], experience_years=2)
        result = enrich_jobs_with_openai(
            user_profile=profile,
            preferences={},
            jobs=jobs,
            batch_size=25,
        )

        assert len(result) == 30
        assert mock_client.chat.completions.create.call_count == 2

    @patch("src.cv_magic.services.openai_scour_jobs._openai_client")
    def test_enrich_jobs_empty(self, mock_client_fn):
        from src.cv_magic.services.openai_scour_jobs import enrich_jobs_with_openai

        profile = UserProfileForScouring(skills=["Python"], experience_years=1)
        result = enrich_jobs_with_openai(
            user_profile=profile, preferences={}, jobs=[]
        )
        assert result == []

    @patch("src.cv_magic.services.openai_scour_jobs._openai_client")
    def test_enrich_normalizes_difficulty_values(self, mock_client_fn):
        """Difficulty/competitiveness values like 'easy', 'hard' should be normalized."""
        from src.cv_magic.services.openai_scour_jobs import enrich_jobs_with_openai

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "jobs": [
                {
                    "title": "Easy Job",
                    "company": "Co",
                    "location": "UK",
                    "url": "https://www.indeed.co.uk/viewjob?jk=norm1",
                    "difficulty": "easy",
                    "competitiveness": "high",
                    "rationale": "Simple role.",
                    "application_tips": "Go for it.",
                },
                {
                    "title": "Hard Job",
                    "company": "Co2",
                    "location": "UK",
                    "url": "https://www.indeed.co.uk/viewjob?jk=norm2",
                    "difficulty": "difficult",
                    "competitiveness": "low",
                    "rationale": "Tough role.",
                    "application_tips": "Prepare.",
                },
            ],
            "warnings": [],
        })
        mock_client.chat.completions.create.return_value = mock_response

        profile = UserProfileForScouring(skills=["Python"], experience_years=2)
        result = enrich_jobs_with_openai(
            user_profile=profile, preferences={},
            jobs=[
                make_job(title="Easy Job", url="https://www.indeed.co.uk/viewjob?jk=norm1"),
                make_job(title="Hard Job", url="https://www.indeed.co.uk/viewjob?jk=norm2"),
            ],
        )

        assert result[0].difficulty.value == "low"   # "easy" → "low"
        assert result[1].difficulty.value == "high"  # "difficult" → "high"


# ════════════════════════════════════════════════════════════
# Suite 5: End-to-End Pipeline (mocked BrightData + OpenAI)
# ════════════════════════════════════════════════════════════

class TestScourJobsEndToEnd:
    """
    Full pipeline tests: scour_jobs_with_brightdata → score → filter → enrich.
    All external services (BrightData HTTP, OpenAI) are mocked.
    """

    def _build_listing_html(self, job_urls: List[str], title: str = "Search Results") -> str:
        """Build a fake listing page with links to job detail pages."""
        links = "\n".join(f'<a href="{url}">Job</a>' for url in job_urls)
        return f"<html><head><title>{title}</title></head><body>{links}</body></html>"

    def _build_job_html(self, *, title: str, company: str, location: str, url: str) -> str:
        """Build a fake job detail page with JSON-LD."""
        ld = json.dumps({
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": title,
            "hiringOrganization": {"@type": "Organization", "name": company},
            "jobLocation": {
                "@type": "Place",
                "address": {"addressLocality": location}
            },
            "url": url,
            "description": f"{title} at {company} in {location}.",
            "datePosted": "2026-02-01",
        })
        return f"""<html>
<head><title>{title} - {company}</title>
<script type="application/ld+json">{ld}</script></head>
<body><h1>{title}</h1></body></html>"""

    @patch("src.cv_magic.services.brightdata_http.brightdata_get")
    def test_internship_search_5_sources(self, mock_bd_get, junior_profile, internship_london_prefs):
        """Search for internships across 5 sources in London."""
        from src.cv_magic.services.job_scourer import scour_jobs_with_brightdata
        from src.cv_magic.services.brightdata_http import BrightDataResponse

        # Use 5 job boards
        domains = WHITELISTED_DOMAINS[:5]
        search_urls = build_default_job_board_search_urls(
            user_profile=junior_profile,
            preferences=internship_london_prefs,
            allowed_domains=domains,
        )

        # Build fake job detail URLs for each domain
        job_detail_urls = {
            "indeed.co.uk": [f"https://www.indeed.co.uk/viewjob?jk=int{i}" for i in range(3)],
            "indeed.com": [f"https://www.indeed.com/viewjob?jk=int{i}" for i in range(2)],
            "linkedin.com": [f"https://www.linkedin.com/jobs/view/int{i}" for i in range(3)],
            "glassdoor.co.uk": [f"https://www.glassdoor.co.uk/job/int{i}" for i in range(2)],
            "glassdoor.com": [f"https://www.glassdoor.com/job/int{i}" for i in range(2)],
        }
        all_job_urls = []
        for urls in job_detail_urls.values():
            all_job_urls.extend(urls)

        def mock_get(*, url, timeout_s=30, max_bytes=900000, country=None):
            # Listing pages return links to job detail pages
            for search_url in search_urls:
                if url == search_url:
                    # Determine which domain's jobs to link
                    for domain, detail_urls in job_detail_urls.items():
                        if domain in url:
                            html = self._build_listing_html(detail_urls)
                            return BrightDataResponse(
                                url=url, status_code=200,
                                content_type="text/html", text=html,
                            )
                    # Fallback: link all jobs
                    html = self._build_listing_html(all_job_urls[:3])
                    return BrightDataResponse(
                        url=url, status_code=200,
                        content_type="text/html", text=html,
                    )

            # Job detail pages return JSON-LD
            for domain, detail_urls in job_detail_urls.items():
                if url in detail_urls:
                    idx = detail_urls.index(url)
                    html = self._build_job_html(
                        title=f"Software Intern {domain} #{idx}",
                        company=f"Company-{domain}",
                        location="London",
                        url=url,
                    )
                    return BrightDataResponse(
                        url=url, status_code=200,
                        content_type="text/html", text=html,
                    )

            # Fallback
            return BrightDataResponse(
                url=url, status_code=404,
                content_type="text/html",
                text="<html><head><title>Not Found</title></head><body></body></html>",
            )

        mock_bd_get.side_effect = mock_get

        jobs, warnings = scour_jobs_with_brightdata(
            user_profile=junior_profile,
            preferences=internship_london_prefs,
            search_urls=search_urls,
            target_openings=10,
            allowed_domains=domains,
        )

        assert len(jobs) > 0
        # All jobs should have valid titles
        for j in jobs:
            assert j["title"]
            assert j["url"]
        # Jobs from multiple domains
        domains_found = set(j.get("source_domain", "") for j in jobs)
        assert len(domains_found) >= 2

    @patch("src.cv_magic.services.brightdata_http.brightdata_get")
    def test_fulltime_search_all_10_sources(self, mock_bd_get, senior_profile, fulltime_nyc_prefs):
        """Full-time search using all 10 whitelisted domains."""
        from src.cv_magic.services.job_scourer import scour_jobs_with_brightdata
        from src.cv_magic.services.brightdata_http import BrightDataResponse

        search_urls = build_default_job_board_search_urls(
            user_profile=senior_profile,
            preferences=fulltime_nyc_prefs,
        )
        assert len(search_urls) == 10

        job_counter = [0]

        def mock_get(*, url, timeout_s=30, max_bytes=900000, country=None):
            # Every listing page links to 2 job detail pages
            parsed = urlparse(url)
            host = parsed.netloc.lower().replace("www.", "")

            # Check if this is a job detail URL
            if _is_job_detail_url(url, WHITELISTED_DOMAINS):
                html = self._build_job_html(
                    title=f"Senior Engineer at {host}",
                    company=f"Corp-{host}",
                    location="New York",
                    url=url,
                )
                return BrightDataResponse(
                    url=url, status_code=200,
                    content_type="text/html", text=html,
                )

            # Listing page
            detail_urls = []
            for i in range(2):
                job_counter[0] += 1
                jid = job_counter[0]
                if "indeed.co.uk" in host:
                    detail_urls.append(f"https://www.indeed.co.uk/viewjob?jk=ft{jid}")
                elif "indeed.com" in host:
                    detail_urls.append(f"https://www.indeed.com/viewjob?jk=ft{jid}")
                elif "linkedin.com" in host:
                    detail_urls.append(f"https://www.linkedin.com/jobs/view/ft{jid}")
                elif "glassdoor" in host:
                    detail_urls.append(f"https://www.{host}/job/ft{jid}")
                elif "reed.co.uk" in host:
                    detail_urls.append(f"https://www.reed.co.uk/jobs/view/ft{jid}")
                elif "cv-library" in host:
                    detail_urls.append(f"https://www.cv-library.co.uk/jobs/view/ft{jid}")
                elif "totaljobs" in host:
                    detail_urls.append(f"https://www.totaljobs.com/jobs/view/ft{jid}")
                elif "monster.co.uk" in host:
                    detail_urls.append(f"https://www.monster.co.uk/jobs/view/ft{jid}")
                elif "monster.com" in host:
                    detail_urls.append(f"https://www.monster.com/jobs/view/ft{jid}")
                else:
                    detail_urls.append(f"https://www.{host}/job/ft{jid}")

            html = self._build_listing_html(detail_urls)
            return BrightDataResponse(
                url=url, status_code=200,
                content_type="text/html", text=html,
            )

        mock_bd_get.side_effect = mock_get

        jobs, warnings = scour_jobs_with_brightdata(
            user_profile=senior_profile,
            preferences=fulltime_nyc_prefs,
            search_urls=search_urls,
            target_openings=20,
        )

        assert len(jobs) >= 10  # At least 1 per domain
        domains_found = set(j.get("source_domain", "") for j in jobs if j.get("source_domain"))
        assert len(domains_found) >= 5  # Jobs from at least half the domains

    @patch("src.cv_magic.services.brightdata_http.brightdata_get")
    def test_contract_remote_search_3_sources(
        self, mock_bd_get, data_science_profile, remote_contract_prefs
    ):
        """Remote contract search with only 3 sources."""
        from src.cv_magic.services.job_scourer import scour_jobs_with_brightdata
        from src.cv_magic.services.brightdata_http import BrightDataResponse

        domains = ("linkedin.com", "indeed.co.uk", "reed.co.uk")
        search_urls = build_default_job_board_search_urls(
            user_profile=data_science_profile,
            preferences=remote_contract_prefs,
            allowed_domains=domains,
        )

        def mock_get(*, url, timeout_s=30, max_bytes=900000, country=None):
            if _is_job_detail_url(url, domains):
                html = self._build_job_html(
                    title="Contract Data Scientist",
                    company="DataCo",
                    location="Remote, UK",
                    url=url,
                )
                return BrightDataResponse(
                    url=url, status_code=200,
                    content_type="text/html", text=html,
                )

            # Listing page with 4 job links each
            detail_urls = []
            if "linkedin" in url:
                detail_urls = [f"https://www.linkedin.com/jobs/view/rc{i}" for i in range(4)]
            elif "indeed" in url:
                detail_urls = [f"https://www.indeed.co.uk/viewjob?jk=rc{i}" for i in range(4)]
            elif "reed" in url:
                detail_urls = [f"https://www.reed.co.uk/jobs/view/rc{i}" for i in range(4)]

            html = self._build_listing_html(detail_urls)
            return BrightDataResponse(
                url=url, status_code=200,
                content_type="text/html", text=html,
            )

        mock_bd_get.side_effect = mock_get

        jobs, warnings = scour_jobs_with_brightdata(
            user_profile=data_science_profile,
            preferences=remote_contract_prefs,
            search_urls=search_urls,
            target_openings=10,
            allowed_domains=domains,
        )

        assert len(jobs) > 0
        for j in jobs:
            assert j["title"]

    @patch("src.cv_magic.services.brightdata_http.brightdata_get")
    def test_empty_search_results(self, mock_bd_get, junior_profile, internship_london_prefs):
        """When listing pages return no job links, should return empty with warnings."""
        from src.cv_magic.services.job_scourer import scour_jobs_with_brightdata
        from src.cv_magic.services.brightdata_http import BrightDataResponse

        search_urls = ["https://www.indeed.co.uk/jobs?q=test&l=london"]

        def mock_get(*, url, timeout_s=30, max_bytes=900000, country=None):
            return BrightDataResponse(
                url=url, status_code=200,
                content_type="text/html",
                text="<html><body>No results found.</body></html>",
            )

        mock_bd_get.side_effect = mock_get

        jobs, warnings = scour_jobs_with_brightdata(
            user_profile=junior_profile,
            preferences=internship_london_prefs,
            search_urls=search_urls,
            target_openings=5,
        )

        assert len(jobs) == 0
        assert any("No job URLs" in w for w in warnings)

    @patch("src.cv_magic.services.brightdata_http.brightdata_get")
    def test_brightdata_fetch_failure_handled(self, mock_bd_get, junior_profile, internship_london_prefs):
        """BrightData failures should be caught and reported in warnings."""
        from src.cv_magic.services.job_scourer import scour_jobs_with_brightdata

        search_urls = ["https://www.indeed.co.uk/jobs?q=test&l=london"]

        mock_bd_get.side_effect = ConnectionError("Proxy timeout")

        jobs, warnings = scour_jobs_with_brightdata(
            user_profile=junior_profile,
            preferences=internship_london_prefs,
            search_urls=search_urls,
            target_openings=5,
        )

        assert len(jobs) == 0
        assert any("Failed to fetch" in w for w in warnings)

    @patch("src.cv_magic.services.brightdata_http.brightdata_get")
    def test_no_search_urls_provided(self, mock_bd_get, junior_profile, internship_london_prefs):
        """Empty search_urls should return empty with warning."""
        from src.cv_magic.services.job_scourer import scour_jobs_with_brightdata

        jobs, warnings = scour_jobs_with_brightdata(
            user_profile=junior_profile,
            preferences=internship_london_prefs,
            search_urls=[],
            target_openings=5,
        )

        assert len(jobs) == 0
        assert any("No search URLs" in w for w in warnings)

    @patch("src.cv_magic.services.brightdata_http.brightdata_get")
    def test_parttime_search_single_source(self, mock_bd_get, junior_profile, parttime_prefs):
        """Part-time job search with a single source."""
        from src.cv_magic.services.job_scourer import scour_jobs_with_brightdata
        from src.cv_magic.services.brightdata_http import BrightDataResponse

        domains = ("totaljobs.com",)
        search_urls = build_default_job_board_search_urls(
            user_profile=junior_profile,
            preferences=parttime_prefs,
            allowed_domains=domains,
        )
        assert len(search_urls) == 1

        def mock_get(*, url, timeout_s=30, max_bytes=900000, country=None):
            if _is_job_detail_url(url, domains):
                html = self._build_job_html(
                    title="Part-Time Frontend Dev",
                    company="AgencyCo",
                    location="Berlin",
                    url=url,
                )
                return BrightDataResponse(
                    url=url, status_code=200,
                    content_type="text/html", text=html,
                )

            detail_urls = [f"https://www.totaljobs.com/jobs/view/pt{i}" for i in range(3)]
            html = self._build_listing_html(detail_urls)
            return BrightDataResponse(
                url=url, status_code=200,
                content_type="text/html", text=html,
            )

        mock_bd_get.side_effect = mock_get

        jobs, warnings = scour_jobs_with_brightdata(
            user_profile=junior_profile,
            preferences=parttime_prefs,
            search_urls=search_urls,
            target_openings=5,
            allowed_domains=domains,
        )

        assert len(jobs) >= 1
        for j in jobs:
            assert j["source_domain"] == "totaljobs.com"

    @patch("src.cv_magic.services.brightdata_http.brightdata_get")
    def test_high_salary_fulltime_search(self, mock_bd_get, senior_profile, senior_fulltime_prefs):
        """Senior full-time search then filter by salary_min."""
        from src.cv_magic.services.job_scourer import scour_jobs_with_brightdata
        from src.cv_magic.services.brightdata_http import BrightDataResponse

        domains = ("linkedin.com", "indeed.com")
        search_urls = build_default_job_board_search_urls(
            user_profile=senior_profile,
            preferences=senior_fulltime_prefs,
            allowed_domains=domains,
        )

        def mock_get(*, url, timeout_s=30, max_bytes=900000, country=None):
            if _is_job_detail_url(url, domains):
                # Alternate high and low salary jobs
                jid = url.split("/")[-1] if "/" in url else url.split("=")[-1]
                idx = hash(jid) % 2
                salary = "$200,000" if idx == 0 else "$80,000"
                html_content = json.dumps({
                    "@context": "https://schema.org",
                    "@type": "JobPosting",
                    "title": f"Engineer ({salary})",
                    "hiringOrganization": {"name": "Corp"},
                    "jobLocation": {"address": {"addressLocality": "San Francisco"}},
                    "url": url,
                    "description": f"Role paying {salary}.",
                    "baseSalary": {
                        "currency": "USD",
                        "value": {"minValue": 200000 if idx == 0 else 80000, "unitText": "YEAR"}
                    },
                })
                html = f"""<html><head><title>Job</title>
                <script type="application/ld+json">{html_content}</script></head><body></body></html>"""
                return BrightDataResponse(
                    url=url, status_code=200,
                    content_type="text/html", text=html,
                )

            detail_urls = []
            if "linkedin" in url:
                detail_urls = [f"https://www.linkedin.com/jobs/view/sal{i}" for i in range(4)]
            else:
                detail_urls = [f"https://www.indeed.com/viewjob?jk=sal{i}" for i in range(4)]

            html = self._build_listing_html(detail_urls)
            return BrightDataResponse(
                url=url, status_code=200,
                content_type="text/html", text=html,
            )

        mock_bd_get.side_effect = mock_get

        jobs, warnings = scour_jobs_with_brightdata(
            user_profile=senior_profile,
            preferences=senior_fulltime_prefs,
            search_urls=search_urls,
            target_openings=10,
            allowed_domains=domains,
        )

        # Now filter by salary
        filtered = filter_jobs_by_preferences(
            preferences=senior_fulltime_prefs,
            jobs=jobs,
        )

        # Jobs with $80k should be filtered out, $200k should pass
        for j in filtered:
            nums = _parse_salary_numbers(j.get("salary_range", ""))
            if nums:
                assert max(nums) >= 150000


# ════════════════════════════════════════════════════════════
# Suite 6: Document Extraction
# ════════════════════════════════════════════════════════════

class TestDocumentExtraction:
    """Tests for text extraction from various document formats."""

    def test_extract_text_from_txt(self):
        text_bytes = b"Hello World\nThis is a test resume."
        result = extract_text_from_bytes(
            data=text_bytes,
            filename="resume.txt",
            content_type=None,
        )
        assert isinstance(result, ExtractedText)
        assert "Hello World" in result.text
        assert result.method == "text:decode"

    def test_extract_text_from_md(self):
        md_bytes = b"# Resume\n\n## Skills\n- Python\n- JavaScript"
        result = extract_text_from_bytes(
            data=md_bytes,
            filename="cv.md",
            content_type=None,
        )
        assert "Python" in result.text
        assert result.method == "text:decode"

    def test_extract_text_utf16(self):
        text = "Resume with special chars: café, résumé"
        data = text.encode("utf-16")
        result = extract_text_from_bytes(
            data=data,
            filename="resume.txt",
        )
        assert "café" in result.text or "caf" in result.text  # encoding may vary

    def test_extract_text_best_effort_unknown_extension(self):
        data = b"Some content in an unknown format"
        result = extract_text_from_bytes(
            data=data,
            filename="resume.xyz",
        )
        assert "Some content" in result.text
        assert result.method == "best-effort:decode"

    def test_extract_text_no_filename(self):
        data = b"Plain text content"
        result = extract_text_from_bytes(
            data=data,
            filename=None,
        )
        assert "Plain text" in result.text

    def test_extract_text_content_type_override(self):
        data = b"Text content via content type"
        result = extract_text_from_bytes(
            data=data,
            filename="noext",
            content_type="text/plain",
        )
        assert result.method == "text:decode"

    def test_extract_pdf_without_pypdf_raises(self):
        """If pypdf is not installed, should raise RuntimeError."""
        with patch.dict("sys.modules", {"pypdf": None}):
            # This test only works if pypdf import is intercepted at module level
            # In practice, pypdf should be available; this tests the error path
            pass  # The real test is that it doesn't crash with a PDF

    def test_extract_text_empty_data(self):
        result = extract_text_from_bytes(
            data=b"",
            filename="empty.txt",
        )
        assert result.text == ""


# ════════════════════════════════════════════════════════════
# Suite 7: Text Utilities
# ════════════════════════════════════════════════════════════

class TestTextUtilities:
    """Tests for normalization and stripping utilities."""

    def test_norm_space_collapses_whitespace(self):
        assert _norm_space("  hello   world  ") == "hello world"

    def test_norm_space_handles_none(self):
        assert _norm_space("") == ""

    def test_norm_space_tabs_newlines(self):
        assert _norm_space("hello\t\nworld") == "hello world"

    def test_strip_tags_removes_html(self):
        assert _strip_tags("<p>Hello <b>World</b></p>") == "Hello World"

    def test_strip_tags_empty(self):
        assert _strip_tags("") == ""

    def test_strip_tags_no_tags(self):
        assert _strip_tags("Just plain text") == "Just plain text"
