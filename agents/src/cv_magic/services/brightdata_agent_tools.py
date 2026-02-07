"""
BrightData HTML parsing utilities for CV Magic.

Extracts structured data from HTML responses.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urljoin, urlparse


_SCRIPT_LD_JSON_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)

_TAG_RE = re.compile(r"<[^>]+>")

_WS_RE = re.compile(r"\s+")


def _strip_tags(html: str) -> str:
    text = _TAG_RE.sub(" ", html)
    text = _WS_RE.sub(" ", text).strip()
    return text


def _extract_title(html: str) -> str:
    m = _TITLE_RE.search(html)
    if not m:
        return ""
    t = m.group(1)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:300]


def _extract_json_ld(html: str, limit: int = 5, max_chars_each: int = 10_000) -> List[str]:
    out: List[str] = []
    for match in _SCRIPT_LD_JSON_RE.finditer(html):
        data = match.group(1).strip()
        if not data:
            continue
        out.append(data[:max_chars_each])
        if len(out) >= limit:
            break
    return out


def _extract_links(base_url: str, html: str, limit: int = 120) -> List[str]:
    parsed = urlparse(base_url)
    base_origin = f"{parsed.scheme}://{parsed.netloc}"
    out: List[str] = []
    seen = set()
    for m in _HREF_RE.finditer(html):
        href = m.group(1).strip()
        if not href or href.startswith("#"):
            continue
        if href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        abs_url = href
        if href.startswith("/"):
            abs_url = urljoin(base_origin, href)
        elif href.startswith("http://") or href.startswith("https://"):
            abs_url = href
        else:
            abs_url = urljoin(base_url, href)

        if abs_url in seen:
            continue
        seen.add(abs_url)
        out.append(abs_url)
        if len(out) >= limit:
            break
    return out


def parse_html_payload(
    *,
    url: str,
    html: str,
    status_code: int,
    content_type: str,
    text_excerpt_chars: int = 12_000,
    link_limit: int = 120,
    json_ld_limit: int = 5,
    json_ld_max_chars_each: int = 10_000,
) -> Dict[str, Any]:
    """
    Parse HTML into a structured payload with:
    - title
    - json_ld blocks (often contains JobPosting)
    - text_excerpt
    - links (absolute URLs)
    """
    title = _extract_title(html)
    json_ld = _extract_json_ld(html, limit=json_ld_limit, max_chars_each=json_ld_max_chars_each)

    # Rough HTML -> text conversion
    text_excerpt = _strip_tags(html)[:text_excerpt_chars]
    links = _extract_links(url, html, limit=link_limit)

    return {
        "url": url,
        "status_code": int(status_code or 0),
        "content_type": str(content_type or ""),
        "title": title,
        "json_ld": json_ld,
        "text_excerpt": text_excerpt,
        "links": links,
    }


def brightdata_fetch_page(
    *,
    url: str,
    timeout_s: int = 30,
    max_bytes: int = 750_000,
    text_excerpt_chars: int = 12_000,
) -> Dict[str, Any]:
    """
    Fetches a page via BrightData proxy and returns a compact, LLM-friendly payload.
    """
    from .brightdata_http import brightdata_get
    
    resp = brightdata_get(url=url, timeout_s=timeout_s, max_bytes=max_bytes)
    return parse_html_payload(
        url=resp.url,
        html=resp.text or "",
        status_code=resp.status_code,
        content_type=resp.content_type,
        text_excerpt_chars=text_excerpt_chars,
    )
