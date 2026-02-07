#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
job_finder.py  --  Natural-language job search powered by BrightData + OpenAI.

Usage:
    python3 job_finder.py "find 5 AI research internships in London"
    python3 job_finder.py "10 software engineering grad jobs in Berlin"

It does NOT hallucinate listings.  Every result comes from a real job board
scraped live through BrightData, then summarised by OpenAI.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import math
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import quote_plus, urlparse, urljoin
from pathlib import Path

# ---------- load .env from agents/.env ----------
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip("'\"")
        os.environ.setdefault(k, v)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("job_finder")


# ================================================================
#  1.  BrightData HTTP proxy client  (from brightdata_http.py)
# ================================================================

@dataclass(frozen=True)
class _ProxyResp:
    url: str
    status_code: int
    content_type: str
    text: str


def _proxy_get(url: str, timeout_s: int = 30, max_bytes: int = 900_000,
               country: Optional[str] = None) -> _ProxyResp:
    """
    Fetch a URL through BrightData.
    
    The .env is configured for the 'scraping_browser1' zone which uses
    WSS/CDP on port 9222.  For plain HTTP scraping we switch to the
    standard Web Unlocker proxy endpoint (port 22225) which works with
    requests over HTTP CONNECT.
    """
    import requests

    username = os.getenv("BRIGHT_DATA_USERNAME", "")
    password = os.getenv("BRIGHT_API_PASSWORD") or os.getenv("BRIGHT_DATA_API_KEY") or ""
    if not username or not password:
        raise RuntimeError("BRIGHT_DATA_USERNAME / BRIGHT_API_PASSWORD not set")

    # The scraping_browser zone (port 9222) is WSS-only.
    # For HTTP proxy we need port 22225 (datacenter/residential) or 33335 (unlocker).
    # Replace zone name to use a compatible zone, or just use port 22225.
    u = username.strip()
    c = (country or os.getenv("BRIGHT_DATA_COUNTRY", "")).strip().lower()
    if c and "-country-" not in u:
        u = u + "-country-" + c

    # Use port 33335 for Web Unlocker (works with scraping_browser credentials)
    port = "33335"
    proxy_url = "http://{}:{}@brd.superproxy.io:{}".format(u, password, port)
    proxies = {"http": proxy_url, "https": proxy_url}

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
    }

    # Try multiple ports if the first one fails
    last_err = None
    for try_port in ("33335", "22225"):
        proxy_url = "http://{}:{}@brd.superproxy.io:{}".format(u, password, try_port)
        proxies = {"http": proxy_url, "https": proxy_url}
        try:
            resp = requests.get(url, headers=headers, proxies=proxies,
                                timeout=timeout_s, stream=True, verify=False)
            chunks = []
            size = 0
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                chunks.append(chunk)
                size += len(chunk)
                if size >= max_bytes:
                    break
            raw = b"".join(chunks)
            ct = (resp.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
            text = raw.decode(resp.encoding or "utf-8", errors="replace")
            return _ProxyResp(url=str(resp.url), status_code=resp.status_code,
                              content_type=ct, text=text)
        except Exception as e:
            last_err = e
            log.warning("Port %s failed for %s: %s", try_port, url[:60], e)
            continue

    # Last resort: try direct (no proxy) -- works for LinkedIn public pages
    try:
        log.info("Trying direct fetch (no proxy) for %s", url[:80])
        resp = requests.get(url, headers=headers, timeout=timeout_s, stream=True)
        chunks = []
        size = 0
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            chunks.append(chunk)
            size += len(chunk)
            if size >= max_bytes:
                break
        raw = b"".join(chunks)
        ct = (resp.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
        text = raw.decode(resp.encoding or "utf-8", errors="replace")
        return _ProxyResp(url=str(resp.url), status_code=resp.status_code,
                          content_type=ct, text=text)
    except Exception as e2:
        raise last_err or e2


# ================================================================
#  2.  HTML parser  (from brightdata_agent_tools.py)
# ================================================================

_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip(html: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html or "")).strip()


def _parse_page(url: str, html: str) -> Dict[str, Any]:
    title_m = _TITLE_RE.search(html)
    title = re.sub(r"\s+", " ", title_m.group(1)).strip()[:300] if title_m else ""

    json_ld = []  # type: List[str]
    for m in _JSONLD_RE.finditer(html):
        d = m.group(1).strip()
        if d:
            json_ld.append(d[:10_000])
        if len(json_ld) >= 5:
            break

    parsed = urlparse(url)
    base_origin = "{}://{}".format(parsed.scheme, parsed.netloc)
    links = []  # type: List[str]
    seen = set()  # type: Set[str]
    for m in _HREF_RE.finditer(html):
        href = m.group(1).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        if href.startswith("/"):
            href = urljoin(base_origin, href)
        elif not href.startswith("http"):
            href = urljoin(url, href)
        # Decode HTML entities in URLs
        href = href.replace("&amp;", "&")
        if href not in seen:
            seen.add(href)
            links.append(href)
        if len(links) >= 150:
            break

    return {
        "url": url, "title": title,
        "json_ld": json_ld,
        "text": _strip(html)[:12_000],
        "links": links,
    }


# ================================================================
#  3.  Domain whitelist + URL classification
# ================================================================

DOMAINS = (
    "linkedin.com", "indeed.co.uk", "indeed.com",
    "glassdoor.co.uk", "glassdoor.com",
    "monster.co.uk", "monster.com",
    "reed.co.uk", "cv-library.co.uk", "totaljobs.com",
)


def _host(url: str) -> str:
    h = urlparse(url).netloc.lower().split("@")[-1]
    return h.split(":", 1)[0] if ":" in h else h


def _whitelisted(url: str) -> bool:
    h = _host(url)
    return any(h == d or h.endswith("." + d) for d in DOMAINS)


_PAGINATION_RE = re.compile(r"[?&](page|p|start|fromage|offset)=[0-9]+", re.I)
_JOB_HINT_RE = re.compile(
    r"(/viewjob|/jobs/view|/job/|/job\?|/position/|/vacancy/|/jobs/[^/]+/\d{4,})", re.I)


def _is_job_url(url: str) -> bool:
    if not _whitelisted(url):
        return False
    path = (urlparse(url).path or "").lower()
    if not path or path in ("/", "/jobs", "/jobs/"):
        return False
    for bad in ("/jobs/jobs-in-", "/job/jobs.htm", "/jobs/search", "/search-jobs"):
        if bad in path:
            return False
    for bad in ("/signin", "/login", "/register", "/companies", "/salary", "/help"):
        if bad in path:
            return False
    if _JOB_HINT_RE.search(path):
        return True
    q = (urlparse(url).query or "").lower()
    return "jk=" in q or "jobid=" in q or "vacancyreference=" in q


# ================================================================
#  4.  JSON-LD JobPosting extraction
# ================================================================

def _find_job_postings(obj):
    # type: (Any) -> List[Dict[str, Any]]
    out = []  # type: List[Dict[str, Any]]
    if isinstance(obj, dict):
        t = obj.get("@type") or obj.get("type") or ""
        if isinstance(t, str) and t.lower() == "jobposting":
            out.append(obj)
        for k in ("@graph", "graph", "mainEntity"):
            if k in obj:
                out.extend(_find_job_postings(obj[k]))
        for v in obj.values():
            if isinstance(v, (dict, list)):
                out.extend(_find_job_postings(v))
    elif isinstance(obj, list):
        for i in obj:
            out.extend(_find_job_postings(i))
    return out


def _job_from_jsonld(jp, fallback_url):
    # type: (Dict[str, Any], str) -> Dict[str, Any]
    title = _WS_RE.sub(" ", str(jp.get("title") or jp.get("name") or "")).strip()

    org = jp.get("hiringOrganization") or {}
    if isinstance(org, list) and org:
        org = org[0]
    company = _WS_RE.sub(" ", str(org.get("name", ""))) if isinstance(org, dict) else ""

    jl = jp.get("jobLocation") or {}
    if isinstance(jl, list) and jl:
        jl = jl[0]
    location = ""
    if isinstance(jl, dict):
        addr = jl.get("address") or {}
        if isinstance(addr, dict):
            parts = [str(addr.get(k, "")) for k in
                     ("addressLocality", "addressRegion", "addressCountry") if addr.get(k)]
            location = ", ".join(parts)

    url = str(jp.get("url") or fallback_url or "")
    posted = str(jp.get("datePosted") or "")

    salary = ""
    bs = jp.get("baseSalary") or {}
    if isinstance(bs, dict):
        cur = bs.get("currency") or ""
        val = bs.get("value") or {}
        if isinstance(val, dict):
            lo = val.get("minValue") or val.get("value") or ""
            hi = val.get("maxValue") or ""
            unit = val.get("unitText") or ""
            salary = "{} {}-{} {}".format(cur, lo, hi, unit).strip() if hi else \
                     "{} {} {}".format(cur, lo, unit).strip()

    desc = _strip(str(jp.get("description") or ""))[:4000]

    return {"title": title, "company": company.strip(), "location": location.strip(),
            "salary": salary, "posted": posted.strip(), "url": url, "description": desc}


def _extract_jobs(payload):
    # type: (Dict[str, Any]) -> List[Dict[str, Any]]
    url = str(payload.get("url") or "")
    jobs = []  # type: List[Dict[str, Any]]
    for raw in (payload.get("json_ld") or []):
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for jp in _find_job_postings(data):
            try:
                jobs.append(_job_from_jsonld(jp, url))
            except Exception:
                pass
    return jobs


# ================================================================
#  5.  Search-URL builder
# ================================================================

def _search_urls(query: str, location: str) -> List[str]:
    q = quote_plus(query)
    loc = quote_plus(location) if location else ""
    loc_slug = re.sub(r"[^a-z0-9]+", "-", location.lower()).strip("-") if location else ""
    urls = []  # type: List[str]
    if loc:
        urls.append("https://www.indeed.co.uk/jobs?q={}&l={}".format(q, loc))
        urls.append("https://www.indeed.com/jobs?q={}&l={}".format(q, loc))
        urls.append("https://www.reed.co.uk/jobs/jobs-in-{}?keywords={}".format(loc_slug, q))
        urls.append("https://www.cv-library.co.uk/search-jobs?keywords={}&location={}".format(q, loc))
        urls.append("https://www.totaljobs.com/jobs?Keywords={}&Location={}".format(q, loc))
        urls.append("https://www.linkedin.com/jobs/search/?keywords={}&location={}".format(q, loc))
        urls.append("https://www.glassdoor.co.uk/Job/jobs.htm?sc.keyword={}".format(q))
    else:
        urls.append("https://www.indeed.co.uk/jobs?q={}".format(q))
        urls.append("https://www.indeed.com/jobs?q={}".format(q))
        urls.append("https://www.reed.co.uk/jobs?keywords={}".format(q))
        urls.append("https://www.linkedin.com/jobs/search/?keywords={}".format(q))
    return [u for u in urls if _whitelisted(u)]


# ================================================================
#  6.  Core scraper  (BrightData -> real listings)
# ================================================================

def scrape_jobs(query, location, num_results=5, max_listing_pages=6,
                max_detail_pages=20, timeout=30):
    # type: (str, str, int, int, int, int) -> Tuple[List[Dict[str, Any]], List[str]]
    """Scrape real job postings from whitelisted boards via BrightData."""
    warnings = []  # type: List[str]
    urls = _search_urls(query, location)
    if not urls:
        return [], ["No search URLs generated"]

    log.info("Search URLs: %s", urls)

    # Phase 1 -- listing pages -> discover job-detail URLs
    listing_q = deque(urls[:8])  # type: Deque[str]
    visited = set()  # type: Set[str]
    job_urls = set()  # type: Set[str]
    fetches = 0

    while listing_q and fetches < max_listing_pages:
        u = listing_q.popleft()
        if u in visited:
            continue
        visited.add(u)
        fetches += 1
        log.info("[listing %d] %s", fetches, u[:120])
        try:
            resp = _proxy_get(u, timeout_s=timeout)
            payload = _parse_page(resp.url, resp.text)
        except Exception as e:
            warnings.append("listing fetch failed: {} ({})".format(u[:80], e))
            continue

        for link in (payload.get("links") or []):
            if _is_job_url(link):
                job_urls.add(link)
            elif _PAGINATION_RE.search(link or "") and _whitelisted(link) and link not in visited:
                if len(listing_q) < 4:
                    listing_q.append(link)

        # Also try extracting jobs directly from listing page JSON-LD
        direct = _extract_jobs(payload)
        if direct:
            for dj in direct:
                if dj.get("title"):
                    job_urls.discard(dj.get("url", ""))  # don't double-fetch

    log.info("Discovered %d job-detail URLs", len(job_urls))

    # Phase 2 -- fetch detail pages
    all_jobs = []  # type: List[Dict[str, Any]]

    # First add any jobs already extracted from listing pages
    for u2 in urls[:8]:
        if u2 in visited:
            continue
    # re-extract from already-visited listing pages
    for u2 in visited:
        try:
            resp = _proxy_get(u2, timeout_s=timeout)
            payload = _parse_page(resp.url, resp.text)
            direct = _extract_jobs(payload)
            all_jobs.extend(direct)
        except Exception:
            pass
        if len(all_jobs) >= num_results * 3:
            break

    detail_fetches = 0
    for job_url in list(job_urls)[:max_detail_pages]:
        if len(all_jobs) >= num_results * 3:
            break
        detail_fetches += 1
        log.info("[detail %d] %s", detail_fetches, job_url[:120])
        try:
            resp = _proxy_get(job_url, timeout_s=timeout)
            payload = _parse_page(resp.url, resp.text)
        except Exception as e:
            warnings.append("detail fetch failed: {} ({})".format(job_url[:80], e))
            continue

        extracted = _extract_jobs(payload)
        if extracted:
            all_jobs.extend(extracted)
        else:
            # Fallback: use page title + text excerpt
            t = (payload.get("title") or "").strip()
            if t and len(t) > 5:
                all_jobs.append({
                    "title": t, "company": "", "location": "",
                    "salary": "", "posted": "",
                    "url": payload.get("url") or job_url,
                    "description": (payload.get("text") or "")[:2000]
                })

    # Deduplicate by URL
    seen_urls = set()  # type: Set[str]
    unique = []  # type: List[Dict[str, Any]]
    for j in all_jobs:
        u3 = j.get("url", "")
        if u3 in seen_urls:
            continue
        seen_urls.add(u3)
        if j.get("title"):
            unique.append(j)

    return unique, warnings


# ================================================================
#  7.  OpenAI: parse natural-language request -> search params
# ================================================================

def _openai_client():
    from openai import OpenAI
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return OpenAI(api_key=key)


def parse_user_request(prompt):
    # type: (str) -> Dict[str, Any]
    """Use OpenAI to turn a free-text request into structured search params."""
    client = _openai_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": (
                "You convert a job-search request into JSON with these keys:\n"
                "  query  (str) -- search string for job boards, e.g. 'AI research internship'\n"
                "  location (str) -- city/country, e.g. 'London' or '' if unspecified\n"
                "  num_results (int) -- how many results the user wants (default 5)\n"
                "Return ONLY valid JSON, nothing else."
            )},
            {"role": "user", "content": prompt},
        ],
    )
    try:
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception:
        return {"query": prompt, "location": "", "num_results": 5}


def summarise_results(prompt, jobs):
    # type: (str, List[Dict[str, Any]]) -> str
    """Use OpenAI to produce a nice summary of the scraped results."""
    if not jobs:
        return "No real job postings were found.  Try broadening the search."

    client = _openai_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    jobs_text = json.dumps(jobs, indent=2, default=str)

    resp = client.chat.completions.create(
        model=model,
        temperature=0.3,
        messages=[
            {"role": "system", "content": (
                "You are a helpful job-search assistant.  The user asked:\n"
                "  \"{}\"\n\n"
                "Below are REAL job postings scraped from job boards.  "
                "Present them clearly and concisely.  "
                "For each job include: number, title, company, location, salary (if available), "
                "posted date (if available), and the REAL application URL.  "
                "Do NOT invent or modify any URLs or details.  "
                "Only present what is in the data.  "
                "If a field is empty, omit it."
            ).format(prompt)},
            {"role": "user", "content": jobs_text},
        ],
    )
    return resp.choices[0].message.content or ""


# ================================================================
#  8.  Main
# ================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 job_finder.py \"find 5 AI research internships in London\"")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])
    print("\n" + "=" * 70)
    print("  JOB FINDER  --  powered by BrightData + OpenAI")
    print("=" * 70)
    print("\nYour request: {}\n".format(prompt))

    # Step 1: parse request with OpenAI
    print("[1/3] Interpreting your request with OpenAI ...")
    params = parse_user_request(prompt)
    query = params.get("query", prompt)
    location = params.get("location", "")
    num = int(params.get("num_results", 5))
    print("  -> query: \"{}\"  location: \"{}\"  num: {}\n".format(query, location, num))

    # Step 2: scrape real postings via BrightData
    print("[2/3] Scraping real job boards via BrightData proxy ...")
    print("  (this takes 30-90 seconds depending on boards)\n")

    t0 = time.time()
    jobs, warnings = scrape_jobs(query, location, num_results=num)
    elapsed = time.time() - t0

    print("\n  Scraped {} raw postings in {:.1f}s".format(len(jobs), elapsed))
    if warnings:
        for w in warnings[:5]:
            log.warning("  %s", w)

    # Step 3: summarise with OpenAI
    final_jobs = jobs[:num]
    print("\n[3/3] Formatting {} results with OpenAI ...\n".format(len(final_jobs)))
    summary = summarise_results(prompt, final_jobs)

    print("=" * 70)
    print(summary)
    print("=" * 70)

    # Also dump raw JSON for programmatic use
    out_path = Path(__file__).parent / "last_results.json"
    out_path.write_text(json.dumps(final_jobs, indent=2, default=str))
    print("\nRaw JSON saved to: {}".format(out_path))


if __name__ == "__main__":
    main()
