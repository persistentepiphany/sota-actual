"""
Shared fixtures for CV Magic / Job Finder test suites.
"""

import json
import math
import pytest
from typing import Any, Dict, List

from src.cv_magic.services.models import (
    ScouredJob,
    ScourPreferences,
    UserProfileForScouring,
)


# ────────────────────────────────────────────────────────────
# User Profiles
# ────────────────────────────────────────────────────────────

@pytest.fixture
def junior_profile() -> UserProfileForScouring:
    """Entry-level candidate profile."""
    return UserProfileForScouring(
        skills=["Python", "JavaScript", "React", "SQL"],
        experience_years=1,
        education="BSc Computer Science, University of London",
        projects=["Portfolio website", "Todo app"],
        links={"github_url": "https://github.com/junior-dev"},
        preferences={},
    )


@pytest.fixture
def senior_profile() -> UserProfileForScouring:
    """Experienced senior engineer profile."""
    return UserProfileForScouring(
        skills=["Python", "Go", "Kubernetes", "AWS", "Terraform", "PostgreSQL", "Redis", "gRPC"],
        experience_years=10,
        education="MSc Software Engineering, Imperial College London",
        projects=["Distributed task scheduler", "Real-time analytics pipeline", "Open-source CLI tool"],
        links={
            "github_url": "https://github.com/senior-eng",
            "linkedin_url": "https://linkedin.com/in/senior-eng",
        },
        preferences={},
    )


@pytest.fixture
def data_science_profile() -> UserProfileForScouring:
    """Data science / ML candidate profile."""
    return UserProfileForScouring(
        skills=["Python", "TensorFlow", "PyTorch", "Pandas", "SQL", "Spark", "NLP"],
        experience_years=4,
        education="MSc Data Science, UCL",
        projects=["Sentiment analysis pipeline", "Recommendation engine"],
        links={},
        preferences={},
    )


# ────────────────────────────────────────────────────────────
# Preferences
# ────────────────────────────────────────────────────────────

@pytest.fixture
def internship_london_prefs() -> Dict[str, Any]:
    return {
        "job_title": "Software Engineer Intern",
        "location": "London",
        "employment_type": "internship",
        "seniority": "intern",
        "remote": False,
    }


@pytest.fixture
def fulltime_nyc_prefs() -> Dict[str, Any]:
    return {
        "job_title": "Software Engineer",
        "location": "New York",
        "employment_type": "full-time",
        "seniority": "mid",
        "remote": False,
    }


@pytest.fixture
def remote_contract_prefs() -> Dict[str, Any]:
    return {
        "job_title": "Data Scientist",
        "location": "United Kingdom",
        "employment_type": "contract",
        "remote": True,
        "include_keywords": ["machine learning", "NLP"],
        "exclude_keywords": ["senior", "lead"],
    }


@pytest.fixture
def parttime_prefs() -> Dict[str, Any]:
    return {
        "job_title": "Frontend Developer",
        "location": "Berlin",
        "employment_type": "part-time",
        "remote": False,
    }


@pytest.fixture
def senior_fulltime_prefs() -> Dict[str, Any]:
    return {
        "job_title": "Senior Backend Engineer",
        "location": "San Francisco",
        "employment_type": "full-time",
        "seniority": "senior",
        "remote": False,
        "salary_min": 150000,
    }


# ────────────────────────────────────────────────────────────
# Synthetic Job Factories
# ────────────────────────────────────────────────────────────

def make_job(
    *,
    title: str = "Software Engineer",
    company: str = "Acme Corp",
    location: str = "London, UK",
    salary_range: str = "£40,000 - £60,000",
    url: str = "https://www.indeed.co.uk/viewjob?jk=abc123",
    source_domain: str = "indeed.co.uk",
    description: str = "Build and maintain web applications.",
    requirements: str = "Python, JavaScript, 2+ years experience.",
    posted_date: str = "2026-02-01",
    relevance_index: int = 75,
) -> Dict[str, Any]:
    """Create a synthetic job dict for testing."""
    return {
        "title": title,
        "company": company,
        "location": location,
        "salary_range": salary_range,
        "posted_date": posted_date,
        "url": url,
        "source_domain": source_domain,
        "description": description,
        "requirements": requirements,
        "relevance_index": relevance_index,
    }


@pytest.fixture
def diverse_job_list() -> List[Dict[str, Any]]:
    """A list of ~20 synthetic jobs spanning multiple types, locations, and sources."""
    jobs = [
        # Internships
        make_job(
            title="Software Engineering Intern",
            company="Google",
            location="London, UK",
            salary_range="£25,000",
            url="https://www.linkedin.com/jobs/view/1001",
            source_domain="linkedin.com",
            description="Summer internship for undergraduates. Remote options available.",
            requirements="Python, algorithms",
        ),
        make_job(
            title="Data Science Intern",
            company="Meta",
            location="New York, NY",
            salary_range="$30,000",
            url="https://www.indeed.com/viewjob?jk=int002",
            source_domain="indeed.com",
            description="ML internship. machine learning, NLP focus.",
            requirements="Python, TensorFlow",
        ),
        make_job(
            title="Marketing Intern",
            company="StartupXYZ",
            location="Berlin, Germany",
            salary_range="€18,000",
            url="https://www.glassdoor.com/job/1003",
            source_domain="glassdoor.com",
            description="Marketing and social media internship.",
            requirements="Communication skills",
        ),
        # Full-time
        make_job(
            title="Full Stack Developer",
            company="Netflix",
            location="Remote",
            salary_range="$120,000 - $160,000",
            url="https://www.linkedin.com/jobs/view/1004",
            source_domain="linkedin.com",
            description="Full-time remote position. React, Node.js, Python.",
            requirements="5+ years full-stack experience",
        ),
        make_job(
            title="Backend Engineer",
            company="Stripe",
            location="San Francisco, CA",
            salary_range="$180,000 - $220,000",
            url="https://www.indeed.com/viewjob?jk=ft005",
            source_domain="indeed.com",
            description="Full-time backend role. Go, microservices.",
            requirements="Go, Kubernetes, 4+ years",
        ),
        make_job(
            title="DevOps Engineer",
            company="AWS",
            location="London, UK",
            salary_range="£80,000 - £110,000",
            url="https://www.reed.co.uk/jobs/view/1006",
            source_domain="reed.co.uk",
            description="Full-time DevOps. Terraform, CI/CD pipelines.",
            requirements="AWS, Docker, Terraform",
        ),
        make_job(
            title="Machine Learning Engineer",
            company="DeepMind",
            location="London, UK",
            salary_range="£90,000 - £130,000",
            url="https://www.linkedin.com/jobs/view/1007",
            source_domain="linkedin.com",
            description="Full-time ML role. machine learning, deep learning, NLP.",
            requirements="PhD or MSc, PyTorch, 3+ years",
        ),
        make_job(
            title="Frontend Developer",
            company="Shopify",
            location="Remote",
            salary_range="$100,000 - $140,000",
            url="https://www.glassdoor.com/job/1008",
            source_domain="glassdoor.com",
            description="Full-time remote frontend. React, TypeScript.",
            requirements="React, 3+ years",
        ),
        # Part-time
        make_job(
            title="Part-Time QA Tester",
            company="TestCo",
            location="Manchester, UK",
            salary_range="£20,000",
            url="https://www.totaljobs.com/jobs/view/1009",
            source_domain="totaljobs.com",
            description="Part-time testing role.",
            requirements="Selenium, manual testing",
        ),
        make_job(
            title="Junior Web Developer (Part-Time)",
            company="AgencyABC",
            location="Berlin, Germany",
            salary_range="€24,000",
            url="https://www.monster.com/jobs/view/1010",
            source_domain="monster.com",
            description="Part-time junior web developer role.",
            requirements="HTML, CSS, JavaScript",
        ),
        # Contract
        make_job(
            title="Contract Data Analyst",
            company="ConsultCo",
            location="London, UK",
            salary_range="£500/day",
            url="https://www.cv-library.co.uk/jobs/view/1011",
            source_domain="cv-library.co.uk",
            description="6-month contract. machine learning data analysis. NLP preferred.",
            requirements="SQL, Python, Tableau",
        ),
        make_job(
            title="Contract Cloud Architect",
            company="CloudFirst",
            location="Remote",
            salary_range="$700/day",
            url="https://www.indeed.co.uk/viewjob?jk=ct012",
            source_domain="indeed.co.uk",
            description="Contract role for cloud migration project.",
            requirements="AWS, Azure, 8+ years",
        ),
        # On-site specific
        make_job(
            title="Embedded Systems Engineer",
            company="RoboTech",
            location="Munich, Germany (onsite)",
            salary_range="€65,000",
            url="https://www.glassdoor.co.uk/job/1013",
            source_domain="glassdoor.co.uk",
            description="On-site embedded systems role. onsite only.",
            requirements="C, C++, RTOS",
        ),
        # High salary
        make_job(
            title="VP of Engineering",
            company="BigTech",
            location="New York, NY",
            salary_range="$350,000 - $500,000",
            url="https://www.linkedin.com/jobs/view/1014",
            source_domain="linkedin.com",
            description="Senior leadership, full-time executive role.",
            requirements="15+ years engineering management",
        ),
        # Low salary
        make_job(
            title="Junior Support Analyst",
            company="HelpDeskInc",
            location="Leeds, UK",
            salary_range="£18,000",
            url="https://www.reed.co.uk/jobs/view/1015",
            source_domain="reed.co.uk",
            description="Entry-level support.",
            requirements="Customer service, basic IT",
        ),
        # Remote flagged
        make_job(
            title="Remote Python Developer",
            company="DistributedCo",
            location="Remote, UK",
            salary_range="£55,000 - £75,000",
            url="https://www.totaljobs.com/jobs/view/1016",
            source_domain="totaljobs.com",
            description="Fully remote Python role.",
            requirements="Python, Django, 2+ years",
        ),
        # Edge case: missing salary
        make_job(
            title="Research Scientist",
            company="LabCorp",
            location="Cambridge, UK",
            salary_range="",
            url="https://www.indeed.co.uk/viewjob?jk=ns017",
            source_domain="indeed.co.uk",
            description="Research role. machine learning focus.",
            requirements="PhD required",
        ),
        # Edge case: very long description
        make_job(
            title="Platform Engineer",
            company="ScaleCo",
            location="London, UK",
            salary_range="£70,000 - £95,000",
            url="https://www.linkedin.com/jobs/view/1018",
            source_domain="linkedin.com",
            description="Platform engineering role. " + "Kubernetes, Docker, Terraform, CI/CD. " * 50,
            requirements="5+ years platform engineering",
        ),
        # Non-whitelisted domain (should be filtered by validation)
        make_job(
            title="Mysterious Job",
            company="Unknown",
            location="Nowhere",
            salary_range="",
            url="https://www.sketchy-site.com/job/999",
            source_domain="sketchy-site.com",
            description="Dubious listing.",
            requirements="None",
        ),
        # Duplicate URL (same as first job)
        make_job(
            title="Software Engineering Intern (Duplicate)",
            company="Google",
            location="London, UK",
            salary_range="£25,000",
            url="https://www.linkedin.com/jobs/view/1001",
            source_domain="linkedin.com",
            description="Duplicate entry.",
            requirements="Python",
        ),
    ]
    return jobs


# ────────────────────────────────────────────────────────────
# HTML Fixtures
# ────────────────────────────────────────────────────────────

@pytest.fixture
def html_with_jsonld_job() -> str:
    """HTML page containing a valid JSON-LD JobPosting."""
    job_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Senior Python Developer",
        "name": "Senior Python Developer",
        "description": "<p>We are looking for a senior Python developer.</p>",
        "hiringOrganization": {
            "@type": "Organization",
            "name": "TechCorp"
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "London",
                "addressRegion": "England",
                "addressCountry": "UK"
            }
        },
        "baseSalary": {
            "@type": "MonetaryAmount",
            "currency": "GBP",
            "value": {
                "@type": "QuantitativeValue",
                "minValue": 70000,
                "maxValue": 95000,
                "unitText": "YEAR"
            }
        },
        "datePosted": "2026-01-15",
        "url": "https://www.indeed.co.uk/viewjob?jk=jsonld001",
        "qualifications": ["Python", "Django", "PostgreSQL"],
    })
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Senior Python Developer - TechCorp | Indeed</title>
    <script type="application/ld+json">{job_ld}</script>
</head>
<body>
    <h1>Senior Python Developer</h1>
    <p>TechCorp is hiring!</p>
    <a href="/viewjob?jk=next001">Next Job</a>
    <a href="https://www.indeed.co.uk/jobs?q=python&l=london&start=10">Page 2</a>
    <a href="https://www.indeed.co.uk/viewjob?jk=detail002">Another Job</a>
    <a href="https://www.linkedin.com/jobs/view/99999">LinkedIn Job</a>
    <a href="/companies/techcorp">Company Profile</a>
    <a href="#top">Back to top</a>
    <a href="javascript:void(0)">No-op</a>
    <a href="mailto:jobs@techcorp.com">Email</a>
</body>
</html>"""


@pytest.fixture
def html_with_multiple_jsonld() -> str:
    """HTML page containing multiple JSON-LD JobPostings (graph)."""
    graph = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "JobPosting",
                "title": "Frontend Engineer",
                "hiringOrganization": {"@type": "Organization", "name": "WebCo"},
                "jobLocation": {
                    "@type": "Place",
                    "address": {"addressLocality": "Berlin", "addressCountry": "Germany"}
                },
                "url": "https://www.glassdoor.com/job/fe001",
                "datePosted": "2026-01-20",
            },
            {
                "@type": "JobPosting",
                "title": "Backend Engineer",
                "hiringOrganization": {"@type": "Organization", "name": "WebCo"},
                "jobLocation": {
                    "@type": "Place",
                    "address": {"addressLocality": "Berlin", "addressCountry": "Germany"}
                },
                "url": "https://www.glassdoor.com/job/be002",
                "datePosted": "2026-01-21",
            },
        ]
    })
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Jobs at WebCo</title>
    <script type="application/ld+json">{graph}</script>
</head>
<body><p>Two jobs at WebCo.</p></body>
</html>"""


@pytest.fixture
def html_no_jsonld() -> str:
    """HTML page with no JSON-LD data at all."""
    return """<!DOCTYPE html>
<html>
<head><title>Boring Page - No Jobs Here</title></head>
<body>
    <h1>Welcome</h1>
    <p>This page has no structured data.</p>
    <a href="https://www.indeed.co.uk/viewjob?jk=link001">Job 1</a>
    <a href="https://www.reed.co.uk/jobs/view/link002">Job 2</a>
    <a href="https://example.com/not-a-job">Not a job</a>
</body>
</html>"""


@pytest.fixture
def html_empty() -> str:
    """Minimal HTML with nothing useful."""
    return "<html><head></head><body></body></html>"


# ────────────────────────────────────────────────────────────
# Embedding helpers
# ────────────────────────────────────────────────────────────

def make_embedding(dim: int = 1536, seed: int = 0) -> List[float]:
    """Create a deterministic unit vector of given dimension."""
    import random
    rng = random.Random(seed)
    raw = [rng.gauss(0, 1) for _ in range(dim)]
    mag = math.sqrt(sum(x * x for x in raw))
    return [x / mag for x in raw] if mag else raw


# ────────────────────────────────────────────────────────────
# Sample CV Text
# ────────────────────────────────────────────────────────────

SAMPLE_CV_TEXT = """
John Smith
London, UK | john@example.com | github.com/johnsmith

EDUCATION
BSc Computer Science, University of London (2024)

EXPERIENCE
Software Engineering Intern — TechStartup Ltd (Jun 2023 – Sep 2023)
- Built REST APIs in Python/Flask
- Wrote unit tests, improved CI/CD pipeline
- Worked with PostgreSQL and Redis

Teaching Assistant — University of London (Sep 2022 – Jun 2023)
- Assisted with Python and Data Structures courses

SKILLS
Python, JavaScript, React, Node.js, SQL, Git, Docker, Flask, REST APIs

PROJECTS
- Portfolio Website: Personal site built with React and Next.js
- Task Manager: Full-stack app with Python backend and React frontend
"""

SAMPLE_CV_BYTES = SAMPLE_CV_TEXT.encode("utf-8")
