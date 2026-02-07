"""
Hackathon Agent Tools

Tools for searching and filtering upcoming hackathon events from the internet.
Uses OpenAI API with web-search capabilities and httpx for scraping.
Only returns future/upcoming hackathons -- never past events.
"""

import os
import json
import logging
from typing import Any
from datetime import datetime, timedelta

from pydantic import Field

from ..shared.tool_base import BaseTool

import httpx

logger = logging.getLogger(__name__)


# ─── Constants ────────────────────────────────────────────────

SEARCH_SOURCES = [
    "https://devpost.com",
    "https://mlh.io/seasons/2026/events",
    "https://www.eventbrite.com",
    "https://lu.ma",
    "https://ethglobal.com",
]

OPENAI_SEARCH_MODEL = "gpt-4o-mini"


# ─── Helpers ─────────────────────────────────────────────────

def _today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _is_upcoming(date_str: str | None) -> bool:
    """Return True if *date_str* is today or in the future (or unparseable)."""
    if not date_str:
        return True  # keep events with unknown dates
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.date() >= datetime.utcnow().date()
    except (ValueError, TypeError):
        return True  # unparseable → keep


def _strip_past(hackathons: list[dict]) -> list[dict]:
    """Remove hackathons whose *end* date (or start date) is in the past."""
    out = []
    for h in hackathons:
        end = h.get("date_end") or h.get("date_start")
        if _is_upcoming(end):
            out.append(h)
    return out


# ─── Tools ────────────────────────────────────────────────────

class SearchHackathonsTool(BaseTool):
    """
    Search the internet for upcoming hackathons by time period, location,
    topics, and mode (online / in-person / both).
    """

    name: str = "search_hackathons"
    description: str = """
    Search the internet for UPCOMING hackathons matching the user's criteria.
    Accepts a time window, location, topic keywords, and whether the user
    wants online, in-person, or both.  Returns a JSON list of hackathon
    objects.  Past events are automatically excluded.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": (
                    "City, region, or country to search near "
                    "(e.g. 'London, UK').  Use 'anywhere' or leave "
                    "empty for a global search."
                ),
            },
            "date_from": {
                "type": "string",
                "description": (
                    "Start of the time window in YYYY-MM-DD.  "
                    "Defaults to today.  Cannot be in the past."
                ),
            },
            "date_to": {
                "type": "string",
                "description": (
                    "End of the time window in YYYY-MM-DD.  "
                    "Defaults to 3 months from today."
                ),
            },
            "topics": {
                "type": "string",
                "description": (
                    "Comma-separated topics or themes the user is "
                    "interested in (e.g. 'blockchain, AI, web3, "
                    "sustainability').  Used to narrow results."
                ),
            },
            "mode": {
                "type": "string",
                "enum": ["online", "in-person", "both"],
                "description": (
                    "Whether the user wants online-only, in-person-only, "
                    "or both types of hackathons.  Defaults to 'both'."
                ),
            },
        },
        "required": [],
    }

    async def execute(
        self,
        location: str = "anywhere",
        date_from: str | None = None,
        date_to: str | None = None,
        topics: str | None = None,
        mode: str = "both",
    ) -> str:
        """Search for hackathons using OpenAI web search + scraper fallback."""
        from openai import AsyncOpenAI

        api_key = os.getenv("OPENAI_API_KEY")

        today = datetime.utcnow()
        today_str = today.strftime("%Y-%m-%d")

        # Clamp date_from to today (never search for the past)
        if not date_from or date_from < today_str:
            date_from = today_str
        if not date_to:
            date_to = (today + timedelta(days=90)).strftime("%Y-%m-%d")

        # Build search clauses
        location_clause = (
            f"located in or near {location}"
            if location and location.lower() not in ("anywhere", "global", "worldwide", "")
            else "anywhere in the world"
        )

        topic_clause = f" focused on {topics}" if topics else ""

        mode_clause = {
            "online": " that are virtual / online only",
            "in-person": " that are in-person / physical only",
            "both": "",
        }.get(mode, "")

        prompt = (
            f"Search the internet for UPCOMING hackathons and coding competitions "
            f"{location_clause} between {date_from} and {date_to}"
            f"{topic_clause}{mode_clause}.\n\n"
            f"CRITICAL: Only include events whose start date is on or after {date_from}. "
            f"Do NOT include any event that has already started or ended before {date_from}.\n\n"
            f"You MUST search ALL of these sources individually:\n"
            f"1. lu.ma -- search 'site:lu.ma hackathon {location}'\n"
            f"2. devpost.com -- search 'site:devpost.com hackathon {location}'\n"
            f"3. mlh.io -- check mlh.io/seasons/2026/events\n"
            f"4. eventbrite.com -- search 'site:eventbrite.com hackathon {location}'\n"
            f"5. ethglobal.com -- check ethglobal.com/events\n"
            f"6. Any other hackathon listing sites you can find\n\n"
            f"Luma (lu.ma) is especially important -- many tech hackathons are "
            f"listed there. Make sure to search it thoroughly.\n\n"
            f"CRITICAL -- URL REQUIREMENTS:\n"
            f"- The 'url' field MUST be the direct link to the event page, NOT a search results page.\n"
            f"- For Luma events use the full lu.ma URL (e.g. https://lu.ma/abc123)\n"
            f"- For Devpost events use the full devpost URL (e.g. https://my-hack.devpost.com/)\n"
            f"- For Eventbrite use the full eventbrite URL\n"
            f"- NEVER use a generic homepage -- always link to the specific event.\n"
            f"- Verify every URL actually exists before including it.\n\n"
            f"CRITICAL -- DATE FILTER:\n"
            f"- Today is {today_str}.\n"
            f"- ONLY include events with date_start >= {date_from}.\n"
            f"- Exclude anything that already happened.\n\n"
            f"Return ONLY a JSON array (no markdown fences) where each element has:\n"
            f'{{"name": "...", "date_start": "YYYY-MM-DD", "date_end": "YYYY-MM-DD", '
            f'"location": "...", "url": "https://direct-link-to-event-page", '
            f'"organizer": "...", "source": "luma|devpost|mlh|eventbrite|ethglobal|other", '
            f'"description": "...", "prizes": "...", "is_virtual": true/false, '
            f'"topics": ["topic1", "topic2"], '
            f'"registration_url": "https://direct-registration-link"}}\n\n'
            f"The 'url' must be a clickable link to the event page. "
            f"The 'registration_url' should be the sign-up / register link if different from 'url'. "
            f"Include the source platform in the 'source' field. "
            f"Set 'is_virtual' to true for online events, false for in-person. "
            f"Include relevant topic tags in 'topics'. "
            f"If you cannot find any, return an empty array []."
        )

        hackathons = []

        try:
            client = AsyncOpenAI(api_key=api_key)

            try:
                response = await client.responses.create(
                    model="gpt-4o-mini",
                    tools=[{"type": "web_search_preview"}],
                    input=prompt,
                )
                raw = ""
                for item in response.output:
                    if hasattr(item, "content"):
                        for block in item.content:
                            if hasattr(block, "text"):
                                raw += block.text
                if not raw.strip():
                    raise ValueError("Empty web search response")
            except Exception as ws_err:
                logger.warning("Web search fallback: %s -- using chat completions", ws_err)
                resp = await client.chat.completions.create(
                    model=os.getenv("LLM_MODEL", OPENAI_SEARCH_MODEL),
                    messages=[
                        {"role": "system", "content": "You are a hackathon research assistant. Return ONLY valid JSON arrays. Never include past events."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )
                raw = resp.choices[0].message.content or "[]"

            # Parse and post-filter
            hackathons = self._extract_json_array(raw)
            hackathons = _strip_past(hackathons)

            # Apply mode filter
            if mode == "online":
                hackathons = [h for h in hackathons if h.get("is_virtual") is True]
            elif mode == "in-person":
                hackathons = [h for h in hackathons if h.get("is_virtual") is not True]

        except Exception as e:
            logger.error("OpenAI hackathon search failed: %s", e)

        # ── Scraper fallback: if few results, try direct web scraping ──
        if len(hackathons) < 2:
            logger.info("Trying direct web scraping fallback (found %d so far)...", len(hackathons))
            scraped = await self._scrape_hackathon_sites(location)
            existing_names = {h.get("name", "").lower().strip()[:50] for h in hackathons}
            for s in scraped:
                name_key = s.get("name", "").lower().strip()[:50]
                if name_key and name_key not in existing_names:
                    hackathons.append(s)
                    existing_names.add(name_key)
            logger.info("After scraping: %d total hackathon(s)", len(hackathons))

        return json.dumps({
            "success": True,
            "count": len(hackathons),
            "hackathons": hackathons,
            "search_params": {
                "location": location,
                "date_from": date_from,
                "date_to": date_to,
                "topics": topics,
                "mode": mode,
            },
        }, indent=2)

    @staticmethod
    async def _scrape_hackathon_sites(location: str) -> list:
        """
        Scrape Devpost, MLH, and Hackathon.com directly as a fallback.
        Runs synchronous scrapers in a thread pool.
        """
        import asyncio

        results = []
        try:
            import sys, os
            agents_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if agents_dir not in sys.path:
                sys.path.insert(0, agents_dir)
            from event_finder import scrape_devpost, scrape_mlh, get_fallback_hackathons

            loop = asyncio.get_event_loop()

            # Run scrapers concurrently in thread pool
            devpost_task = loop.run_in_executor(None, scrape_devpost, location, 5)
            mlh_task = loop.run_in_executor(None, scrape_mlh, location, 5)

            devpost_results, mlh_results = await asyncio.gather(
                devpost_task, mlh_task, return_exceptions=True
            )

            for source_results in [devpost_results, mlh_results]:
                if isinstance(source_results, list):
                    for s in source_results:
                        results.append({
                            "name": s.get("name", ""),
                            "location": s.get("location", "Online"),
                            "date_start": s.get("date", ""),
                            "date_end": s.get("date", ""),
                            "url": s.get("url", ""),
                            "description": s.get("description", ""),
                            "source": s.get("platform", "scraper").lower(),
                            "is_virtual": "online" in s.get("location", "").lower(),
                        })

            # If still nothing, add curated fallback platforms
            if not results:
                fallbacks = get_fallback_hackathons(location, 5)
                for s in fallbacks:
                    results.append({
                        "name": s.get("name", ""),
                        "location": s.get("location", "Online"),
                        "date_start": s.get("date", ""),
                        "date_end": s.get("date", ""),
                        "url": s.get("url", ""),
                        "description": s.get("description", ""),
                        "source": s.get("platform", "curated").lower(),
                        "is_virtual": "online" in s.get("location", "").lower(),
                    })

        except Exception as e:
            logger.warning("Scraping fallback error: %s", e)

        return results

    @staticmethod
    def _extract_json_array(text: str) -> list:
        """Extract a JSON array from possibly markdown-wrapped text."""
        import re
        # Strip markdown code fences
        text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "hackathons" in data:
                return data["hackathons"]
            return [data]
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return []


class ScrapeHackathonDetailsTool(BaseTool):
    """
    Scrape additional details from a hackathon URL.
    """

    name: str = "scrape_hackathon_details"
    description: str = """
    Fetch a hackathon event page and extract detailed information
    such as schedule, requirements, prizes, registration deadlines,
    and tech stack.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the hackathon event page",
            },
        },
        "required": ["url"],
    }

    async def execute(self, url: str) -> str:
        """Scrape hackathon details from a URL using httpx + OpenAI summarisation."""
        from openai import AsyncOpenAI

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=20.0,
                headers={"User-Agent": "SOTA-HackathonAgent/1.0"},
            ) as http:
                resp = await http.get(url)
                resp.raise_for_status()
                html = resp.text[:15_000]

            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            summary = await client.chat.completions.create(
                model=os.getenv("LLM_MODEL", OPENAI_SEARCH_MODEL),
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract hackathon details from this HTML. "
                            "Return JSON with: name, dates, location, description, "
                            "registration_deadline, prizes, tracks, requirements, "
                            "tech_stack, organizer, is_virtual, topics. "
                            "Return ONLY valid JSON, no markdown."
                        ),
                    },
                    {"role": "user", "content": html},
                ],
                temperature=0.1,
            )

            raw = summary.choices[0].message.content or "{}"
            details = json.loads(raw) if raw.strip().startswith("{") else {"raw": raw}

            return json.dumps({
                "success": True,
                "url": url,
                "details": details,
            }, indent=2)

        except httpx.HTTPStatusError as e:
            return json.dumps({"success": False, "error": f"HTTP {e.response.status_code}: {url}"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


class FilterHackathonsTool(BaseTool):
    """
    Filter a list of hackathons by criteria.  Always strips past events.
    """

    name: str = "filter_hackathons"
    description: str = """
    Filter a previously retrieved hackathon list.  Supports:
    - virtual_only / in_person_only
    - keyword / topic match
    - max results
    Past events are always removed automatically.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "hackathons_json": {
                "type": "string",
                "description": "JSON string of the hackathon array to filter",
            },
            "virtual_only": {
                "type": "boolean",
                "description": "If true, keep only virtual / online hackathons",
            },
            "in_person_only": {
                "type": "boolean",
                "description": "If true, keep only in-person / physical hackathons",
            },
            "keyword": {
                "type": "string",
                "description": "Keep only hackathons whose name, description, or topics contain this keyword",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default 10)",
            },
        },
        "required": ["hackathons_json"],
    }

    async def execute(
        self,
        hackathons_json: str,
        virtual_only: bool = False,
        in_person_only: bool = False,
        keyword: str | None = None,
        max_results: int = 10,
    ) -> str:
        """Filter hackathons by criteria. Always removes past events."""
        try:
            hackathons = json.loads(hackathons_json)
        except json.JSONDecodeError:
            return json.dumps({"success": False, "error": "Invalid JSON input"})

        # Always strip past events first
        filtered = _strip_past(hackathons)

        if virtual_only:
            filtered = [h for h in filtered if h.get("is_virtual") is True]

        if in_person_only:
            filtered = [h for h in filtered if h.get("is_virtual") is not True]

        if keyword:
            kw = keyword.lower()
            filtered = [
                h for h in filtered
                if kw in (
                    h.get("name", "") + " "
                    + h.get("description", "") + " "
                    + " ".join(h.get("topics", []))
                ).lower()
            ]

        filtered = filtered[:max_results]

        return json.dumps({
            "success": True,
            "count": len(filtered),
            "hackathons": filtered,
        }, indent=2)


class FormatHackathonResultsTool(BaseTool):
    """
    Format hackathon results into a human-readable summary.
    """

    name: str = "format_hackathon_results"
    description: str = """
    Take a hackathon JSON array and produce a clean, user-friendly
    text summary.  Useful as the final step before responding to the user.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "hackathons_json": {
                "type": "string",
                "description": "JSON string of hackathon results to format",
            },
        },
        "required": ["hackathons_json"],
    }

    async def execute(self, hackathons_json: str) -> str:
        """Format hackathon results as readable text."""
        try:
            hackathons = json.loads(hackathons_json)
        except json.JSONDecodeError:
            return "Could not parse hackathon data."

        # Final safety net: strip past events before display
        hackathons = _strip_past(hackathons)

        if not hackathons:
            return "No upcoming hackathons found matching your criteria."

        count = len(hackathons)
        lines = [f"I found {count} hackathon{'s' if count != 1 else ''} for you:\n"]
        for i, h in enumerate(hackathons, 1):
            name = h.get("name", "Unknown")
            loc = h.get("location", "TBD")
            ds = h.get("date_start", "?")
            de = h.get("date_end", ds)
            url = h.get("url", "")
            reg_url = h.get("registration_url", "")
            prizes = h.get("prizes", "")
            source = h.get("source", "")
            virtual = h.get("is_virtual", False)
            topics = h.get("topics", [])

            mode_tag = "[ONLINE]" if virtual else "[IN-PERSON]"
            lines.append(f"{i}. {name}  {mode_tag}")
            lines.append(f"   Dates: {ds} -> {de}")
            lines.append(f"   Location: {loc}")
            if topics:
                lines.append(f"   Topics: {', '.join(topics)}")
            if prizes:
                lines.append(f"   Prizes: {prizes}")
            if url:
                lines.append(f"   Event: {url}")
            if reg_url and reg_url != url:
                lines.append(f"   Register: {reg_url}")
            if source:
                lines.append(f"   Source: {source}")
            lines.append("")

        lines.append("Want me to help you register for any of these?")
        return "\n".join(lines)


# ─── Factory ──────────────────────────────────────────────────

def create_hackathon_tools() -> list[BaseTool]:
    """Create all hackathon-specific tools."""
    return [
        SearchHackathonsTool(),
        ScrapeHackathonDetailsTool(),
        FilterHackathonsTool(),
        FormatHackathonResultsTool(),
    ]
