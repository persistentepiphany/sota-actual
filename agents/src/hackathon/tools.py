"""
Hackathon Agent Tools

Tools for searching and filtering hackathon events from the internet.
Uses OpenAI API with web-search capabilities and httpx for scraping.
"""

import os
import json
import logging
from typing import Any
from datetime import datetime

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


# ─── Tools ────────────────────────────────────────────────────

class SearchHackathonsTool(BaseTool):
    """
    Search the internet for hackathons by date range and location
    using OpenAI's chat completions with web search grounding.
    """

    name: str = "search_hackathons"
    description: str = """
    Search the internet for upcoming hackathons near a specific location
    and within a date range.  Returns a JSON list of hackathon objects
    with name, date, location, url, description, and prize info.

    Use this tool when the user asks to find hackathons.
    """
    parameters: dict = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City, region, or country to search near (e.g. 'London, UK')",
            },
            "date_from": {
                "type": "string",
                "description": "Start date in YYYY-MM-DD format (default: today)",
            },
            "date_to": {
                "type": "string",
                "description": "End date in YYYY-MM-DD format (default: 3 months from now)",
            },
            "keywords": {
                "type": "string",
                "description": "Optional extra keywords to narrow results (e.g. 'blockchain AI web3')",
            },
        },
        "required": ["location"],
    }

    async def execute(
        self,
        location: str,
        date_from: str | None = None,
        date_to: str | None = None,
        keywords: str | None = None,
    ) -> str:
        """Search for hackathons using OpenAI."""
        from openai import AsyncOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return json.dumps({"success": False, "error": "OPENAI_API_KEY not set"})

        # Default date range: today → +3 months
        today = datetime.utcnow()
        if not date_from:
            date_from = today.strftime("%Y-%m-%d")
        if not date_to:
            from datetime import timedelta
            date_to = (today + timedelta(days=90)).strftime("%Y-%m-%d")

        kw_clause = f" related to {keywords}" if keywords else ""

        prompt = (
            f"Search the internet for upcoming hackathons and coding competitions "
            f"near {location} between {date_from} and {date_to}{kw_clause}.\n\n"
            f"You MUST search ALL of these sources individually:\n"
            f"1. lu.ma — search 'site:lu.ma hackathon {location}'\n"
            f"2. devpost.com — search 'site:devpost.com hackathon {location}'\n"
            f"3. mlh.io — check mlh.io/seasons/2026/events\n"
            f"4. eventbrite.com — search 'site:eventbrite.com hackathon {location}'\n"
            f"5. ethglobal.com — check ethglobal.com/events\n"
            f"6. Any other hackathon listing sites you can find\n\n"
            f"Luma (lu.ma) is especially important — many tech hackathons are "
            f"listed there. Make sure to search it thoroughly.\n\n"
            f"CRITICAL — URL REQUIREMENTS:\n"
            f"- The 'url' field MUST be the direct link to the event page, NOT a search results page.\n"
            f"- For Luma events use the full lu.ma URL (e.g. https://lu.ma/abc123)\n"
            f"- For Devpost events use the full devpost URL (e.g. https://my-hack.devpost.com/)\n"
            f"- For Eventbrite use the full eventbrite URL\n"
            f"- NEVER use a generic homepage — always link to the specific event.\n"
            f"- Verify every URL actually exists before including it.\n\n"
            f"Return ONLY a JSON array (no markdown fences) where each element has:\n"
            f'{{"name": "...", "date_start": "YYYY-MM-DD", "date_end": "YYYY-MM-DD", '
            f'"location": "...", "url": "https://direct-link-to-event-page", '
            f'"organizer": "...", "source": "luma|devpost|mlh|eventbrite|ethglobal|other", '
            f'"description": "...", "prizes": "...", "is_virtual": false, '
            f'"registration_url": "https://direct-registration-link"}}\n\n'
            f"The 'url' must be a clickable link to the event page. "
            f"The 'registration_url' should be the sign-up / register link if different from 'url'. "
            f"Include the source platform in the 'source' field. "
            f"If you cannot find any, return an empty array []."
        )

        try:
            client = AsyncOpenAI(api_key=api_key)

            # Try web-search enabled model first, fall back to regular
            try:
                response = await client.responses.create(
                    model="gpt-4o-mini",
                    tools=[{"type": "web_search_preview"}],
                    input=prompt,
                )
                # Extract text from response output
                raw = ""
                for item in response.output:
                    if hasattr(item, "content"):
                        for block in item.content:
                            if hasattr(block, "text"):
                                raw += block.text
                if not raw.strip():
                    raise ValueError("Empty web search response")
            except Exception as ws_err:
                logger.warning("Web search fallback: %s — using chat completions", ws_err)
                resp = await client.chat.completions.create(
                    model=os.getenv("LLM_MODEL", OPENAI_SEARCH_MODEL),
                    messages=[
                        {"role": "system", "content": "You are a hackathon research assistant. Return ONLY valid JSON arrays."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )
                raw = resp.choices[0].message.content or "[]"

            # Parse the JSON from the response
            hackathons = self._extract_json_array(raw)

            return json.dumps({
                "success": True,
                "count": len(hackathons),
                "hackathons": hackathons,
                "search_params": {
                    "location": location,
                    "date_from": date_from,
                    "date_to": date_to,
                    "keywords": keywords,
                },
            }, indent=2)

        except Exception as e:
            logger.error("Hackathon search failed: %s", e)
            return json.dumps({"success": False, "error": str(e)})

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
            # Try to find the array inside the text
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
                html = resp.text[:15_000]  # limit to avoid token overflow

            # Summarise with OpenAI
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
                            "tech_stack, organizer, is_virtual. "
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
    Filter a list of hackathons by criteria.
    """

    name: str = "filter_hackathons"
    description: str = """
    Filter a previously retrieved hackathon list by criteria such as
    virtual-only, keyword match, or maximum travel distance.
    Returns the filtered list.
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
            "keyword": {
                "type": "string",
                "description": "Keep only hackathons whose name or description contain this keyword",
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
        keyword: str | None = None,
        max_results: int = 10,
    ) -> str:
        """Filter hackathons by criteria."""
        try:
            hackathons = json.loads(hackathons_json)
        except json.JSONDecodeError:
            return json.dumps({"success": False, "error": "Invalid JSON input"})

        filtered = hackathons

        if virtual_only:
            filtered = [h for h in filtered if h.get("is_virtual")]

        if keyword:
            kw = keyword.lower()
            filtered = [
                h for h in filtered
                if kw in (h.get("name", "") + " " + h.get("description", "")).lower()
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

        if not hackathons:
            return "No hackathons found matching your criteria."

        lines = [f"🏆 Found {len(hackathons)} hackathon(s):\n"]
        for i, h in enumerate(hackathons, 1):
            name = h.get("name", "Unknown")
            loc = h.get("location", "TBD")
            ds = h.get("date_start", "?")
            de = h.get("date_end", ds)
            url = h.get("url", "")
            reg_url = h.get("registration_url", "")
            prizes = h.get("prizes", "")
            source = h.get("source", "")
            virtual = " 🌐 Virtual" if h.get("is_virtual") else ""

            lines.append(f"{i}. **{name}**{virtual}")
            lines.append(f"   📅 {ds} → {de}")
            lines.append(f"   📍 {loc}")
            if prizes:
                lines.append(f"   💰 {prizes}")
            if url:
                lines.append(f"   🔗 Event page: {url}")
            if reg_url and reg_url != url:
                lines.append(f"   📝 Register: {reg_url}")
            if source:
                lines.append(f"   📡 Source: {source}")
            lines.append("")

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
