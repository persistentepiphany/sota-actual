"""
BrightData HTTP Client for CV Magic.

Makes HTTP requests through BrightData proxy for web scraping.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Iterable, Optional
from urllib.parse import urlparse

from .job_scourer import is_url_whitelisted


@dataclass(frozen=True)
class BrightDataResponse:
    url: str
    status_code: int
    content_type: str
    text: str


@dataclass(frozen=True)
class BrightDataProxySettings:
    host: str
    port: int
    username: str
    password: str
    country: str


def _build_proxy_username(username: str, country: Optional[str]) -> str:
    u = (username or "").strip()
    if not country:
        return u
    if "-country-" in u:
        return u
    return f"{u}-country-{country.lower()}"


def brightdata_proxy_settings(country_override: Optional[str] = None) -> Optional[BrightDataProxySettings]:
    """Get BrightData proxy settings from environment."""
    api_key = os.getenv("BRIGHT_DATA_API_KEY")
    api_password = os.getenv("BRIGHT_API_PASSWORD")
    username = os.getenv("BRIGHT_DATA_USERNAME")
    country = country_override or os.getenv("BRIGHT_DATA_COUNTRY") or ""

    password = (api_password or api_key or "").strip()
    if not password or not username:
        return None  # No credentials configured

    port_raw = os.getenv("BRIGHT_DATA_PORT")
    if port_raw:
        port = port_raw
    else:
        port = "33335" if "scraping_browser" in (username or "").lower() else "22225"

    proxy_username = _build_proxy_username(username, country or None)
    return BrightDataProxySettings(
        host="brd.superproxy.io",
        port=int(port),
        username=proxy_username,
        password=password,
        country=str(country or "").lower(),
    )


def _proxy_config(country: Optional[str] = None) -> Dict[str, str]:
    s = brightdata_proxy_settings(country_override=country)
    if not s:
        return {}  # No proxy configured
    proxy_url = f"http://{s.username}:{s.password}@{s.host}:{s.port}"
    return {"http": proxy_url, "https": proxy_url}


def brightdata_get(
    *,
    url: str,
    timeout_s: int = 30,
    max_bytes: int = 750_000,
    allowed_domains: Optional[Iterable[str]] = None,
    country: Optional[str] = None,
) -> BrightDataResponse:
    """Fetch a URL through BrightData proxy."""
    if allowed_domains:
        check = is_url_whitelisted(url, allowed_domains=allowed_domains)
        if not check.allowed:
            raise ValueError(f"URL domain not whitelisted: {check.domain}")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http/https URLs are supported")

    try:
        import requests
    except ImportError as e:
        raise RuntimeError("Missing dependency: requests") from e

    proxies = _proxy_config(country=country)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CV-Magic/1.0; +https://example.invalid)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
    }

    resp = requests.get(url, headers=headers, proxies=proxies, timeout=timeout_s, stream=True)

    chunks = []
    size = 0
    for chunk in resp.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        chunks.append(chunk)
        size += len(chunk)
        if size >= max_bytes:
            break

    content = b"".join(chunks)
    content_type = (resp.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    try:
        text = content.decode(resp.encoding or "utf-8", errors="replace")
    except Exception:
        text = content.decode("utf-8", errors="replace")

    return BrightDataResponse(
        url=str(resp.url),
        status_code=int(resp.status_code),
        content_type=content_type,
        text=text,
    )
