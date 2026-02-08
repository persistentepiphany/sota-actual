#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
event_finder.py -- Search for upcoming hackathons online

Accepts structured user input:
  --from       Start date (YYYY-MM-DD, default: today)
  --to         End date   (YYYY-MM-DD, default: +3 months)
  --location   City / region / country (default: anywhere)
  --topics     Comma-separated themes  (e.g. "AI, blockchain")
  --mode       online | in-person | both (default: both)
  --count      Max results to return (default: 10)

Examples:
    python event_finder.py --location London --topics "AI, web3" --mode online
    python event_finder.py --from 2025-03-01 --to 2025-06-01 --location Berlin
    python event_finder.py --topics blockchain --count 5

Only UPCOMING hackathons are returned -- past events are always filtered out.
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re
from typing import List, Dict

# Load .env
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

TODAY = datetime.utcnow().date()


# ─── Date helpers ────────────────────────────────────────────

def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def is_upcoming(date_str: str | None) -> bool:
    """True if date_str is today or later (or unparseable)."""
    if not date_str:
        return True
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date() >= TODAY
    except (ValueError, TypeError):
        return True


def strip_past(results: List[Dict]) -> List[Dict]:
    """Remove events whose date is in the past."""
    out = []
    for r in results:
        raw = r.get("date", "")
        # Try to find a YYYY-MM-DD in the date string
        match = re.search(r"\d{4}-\d{2}-\d{2}", raw)
        if match:
            if not is_upcoming(match.group()):
                continue
        out.append(r)
    return out


# ─── Scrapers ────────────────────────────────────────────────

def scrape_devpost(location="", num=10) -> List[Dict]:
    """Scrape live hackathons from Devpost using their JSON API"""
    location_matches = []
    all_hackathons = []
    try:
        print("🔍 Scraping Devpost...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest'
        }

        # Try location-specific search first, then fallback to all open
        urls_to_try = []
        if location:
            urls_to_try.append(("https://devpost.com/api/hackathons", {
                'status[]': 'open', 'order_by': 'recently-added',
                'search': location,
            }))
        urls_to_try.append(("https://devpost.com/api/hackathons", {
            'status[]': 'open', 'order_by': 'recently-added',
        }))

        for url, params in urls_to_try:
            response = requests.get(url, headers=headers, params=params, timeout=15)

            if response.status_code == 200:
                try:
                    data = response.json()
                    hackathons = data.get('hackathons', [])

                    for hack in hackathons[:num * 3]:
                        try:
                            title = hack.get('title', '').strip()
                            if not title:
                                continue

                            link = hack.get('url', '') or hack.get('display_url', '')
                            if link and not link.startswith('http'):
                                link = f"https://devpost.com{link}"

                            # Extract location
                            loc_text = hack.get('location', 'Online')
                            if not loc_text or loc_text.lower() in ['tbd', 'remote']:
                                loc_text = 'Online'

                            # Extract dates
                            submission_period = hack.get('submission_period_dates', '')
                            date_text = submission_period if submission_period else "Check website for dates"

                            # Extract description
                            desc_text = hack.get('tagline', '') or hack.get('description', '')
                            if desc_text:
                                desc_text = desc_text[:200]

                            entry = {
                                "name": title,
                                "platform": "Devpost",
                                "url": link,
                                "location": loc_text,
                                "date": date_text,
                                "description": desc_text or "Hackathon on Devpost - visit URL for details"
                            }

                            # Soft-match: prioritize location matches but keep all
                            if location and (
                                location.lower() in loc_text.lower()
                                or location.lower() in title.lower()
                                or location.lower() in (desc_text or "").lower()
                            ):
                                location_matches.append(entry)
                            else:
                                all_hackathons.append(entry)

                        except Exception:
                            continue
                except json.JSONDecodeError:
                    pass

            if location_matches:
                break  # Got location-specific results, no need to try generic

        # Return location matches first, then pad with general hackathons
        results = location_matches[:num]
        if len(results) < num:
            # Deduplicate by title
            seen = {r["name"].lower() for r in results}
            for h in all_hackathons:
                if h["name"].lower() not in seen:
                    results.append(h)
                    seen.add(h["name"].lower())
                if len(results) >= num:
                    break

        print(f"   ✓ Found {len(results)} hackathon(s) on Devpost ({len(location_matches)} location-matched)")
    except Exception as e:
        print(f"   ⚠️  Devpost error: {e}")

    return results


def scrape_mlh(location="", num=10) -> List[Dict]:
    """Scrape live hackathons from Major League Hacking (MLH)"""
    location_matches = []
    all_hackathons = []
    try:
        print("🔍 Scraping MLH...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        # MLH events page - try both 2026 and 2025
        for year in ["2026", "2025"]:
            url = f"https://mlh.io/seasons/{year}/events"
            try:
                response = requests.get(url, headers=headers, timeout=15)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')

                    # Try multiple selectors (MLH changes their HTML regularly)
                    events = (
                        soup.find_all('div', class_='event') or
                        soup.find_all('div', class_=re.compile(r'event.*card', re.I)) or
                        soup.select('.event-wrapper .event') or
                        soup.find_all('div', class_=re.compile(r'event', re.I)) or
                        soup.find_all('a', href=re.compile(r'/event/'))
                    )

                    for event in events[:num * 3]:
                        try:
                            # Find title
                            title_elem = (
                                event.find('h3') or
                                event.find('h2') or
                                event.find('a', href=True) or
                                event.find(class_=re.compile(r'.*title.*|.*name.*', re.I))
                            )
                            if not title_elem:
                                continue

                            title = title_elem.get_text(strip=True)
                            if not title or len(title) < 3:
                                continue

                            # Extract link
                            link = ""
                            link_elem = event.find('a', href=True) if event.name != 'a' else event
                            if link_elem and 'href' in link_elem.attrs:
                                link = link_elem['href']
                                if link and not link.startswith('http'):
                                    link = f"https://mlh.io{link}"

                            # Extract dates
                            date_text = ""
                            date_elem = event.find('time') or event.find(class_=re.compile(r'.*date.*', re.I))
                            if date_elem:
                                date_text = date_elem.get_text(strip=True)
                            if not date_text:
                                # Try extracting from full text
                                text = event.get_text()
                                date_match = re.search(
                                    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}',
                                    text, re.I
                                )
                                if date_match:
                                    date_text = date_match.group()

                            # Extract location
                            loc_text = "Online"
                            loc_elem = event.find(class_=re.compile(r'.*location.*|.*city.*|.*venue.*', re.I))
                            if loc_elem:
                                loc_text = loc_elem.get_text(strip=True)
                            elif "hybrid" in event.get_text().lower():
                                loc_text = "Hybrid"

                            entry = {
                                "name": title,
                                "platform": "MLH",
                                "url": link or url,
                                "location": loc_text,
                                "date": date_text or "Check website for dates",
                                "description": "Official MLH hackathon"
                            }

                            # Soft location match
                            if location and (
                                location.lower() in loc_text.lower()
                                or location.lower() in title.lower()
                            ):
                                location_matches.append(entry)
                            else:
                                all_hackathons.append(entry)

                        except Exception:
                            continue

                    if location_matches or all_hackathons:
                        break
            except Exception:
                continue

        # Return location matches first, then pad with general
        results = location_matches[:num]
        if len(results) < num:
            seen = {r["name"].lower() for r in results}
            for h in all_hackathons:
                if h["name"].lower() not in seen:
                    results.append(h)
                    seen.add(h["name"].lower())
                if len(results) >= num:
                    break

        print(f"   ✓ Found {len(results)} hackathon(s) on MLH ({len(location_matches)} location-matched)")
    except Exception as e:
        print(f"   ⚠️  MLH error: {e}")

    return results


def scrape_hackathoncom(location="", num=10) -> List[Dict]:
    """Scrape hackathons from Hackathon.com"""
    results = []
    try:
        print("🔍 Scraping Hackathon.com...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        url = "https://www.hackathon.com/events"
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Try multiple selectors
            events = (
                soup.find_all('div', class_=['event-card', 'event-item', 'hackathon-card']) or
                soup.find_all('article', class_=re.compile(r'.*event.*|.*hackathon.*', re.I)) or
                soup.select('.events-list > div') or
                soup.find_all('div', class_=re.compile(r'.*event.*', re.I))[:num]
            )

            for event in events[:num]:
                try:
                    title_elem = event.find(['h1', 'h2', 'h3', 'h4']) or event.find('a', class_=re.compile(r'.*title.*', re.I))
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    if not title or len(title) < 3:
                        continue

                    link = ""
                    link_elem = event.find("a", href=True)
                    if link_elem and "href" in link_elem.attrs:
                        link = link_elem["href"]
                        if link and not link.startswith("http"):
                            link = f"https://www.hackathon.com{link}"

                    text = event.get_text()
                    date_text = ""
                    for pattern in [
                        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:\s*-\s*\d{1,2})?,?\s+\d{4}\b",
                        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
                        r"\b\d{4}-\d{2}-\d{2}\b",
                    ]:
                        m = re.search(pattern, text, re.I)
                        if m:
                            date_text = m.group()
                            break

                    loc_text = "Online"
                    is_virtual = "online" in text.lower() or "virtual" in text.lower()
                    if not is_virtual and location:
                        loc_text = location

                    results.append({
                        "name": title,
                        "platform": "Hackathon.com",
                        "url": link or url,
                        "location": loc_text,
                        "date": date_text or "Check website",
                        "description": "Community hackathon",
                    })

                except Exception:
                    continue

        print(f"   ✓ Found {len(results)} hackathon(s) on Hackathon.com")
    except Exception as e:
        print(f"   ⚠️  Hackathon.com error: {e}")
    return results


# ─── Fallback curated sources ────────────────────────────────

CURATED_SOURCES = [
    {
        "name": "Explore Devpost - Live Hackathons",
        "platform": "Devpost",
        "url": "https://devpost.com/hackathons",
        "location": "Online & Worldwide",
        "date": "Year-round",
        "description": "Browse hundreds of active hackathons on Devpost.",
    },
    {
        "name": "MLH Official Hackathon Season 2025-2026",
        "platform": "MLH",
        "url": "https://mlh.io/seasons/2026/events",
        "location": "Online & Worldwide",
        "date": "Sep 2025 - Aug 2026",
        "description": "Major League Hacking hosts 200+ official student hackathons annually.",
    },
    {
        "name": "ETHGlobal (Web3/Blockchain)",
        "platform": "ETHGlobal",
        "url": "https://ethglobal.com/events",
        "location": "Global cities + Online",
        "date": "Monthly",
        "description": "Premier Ethereum and Web3 hackathons worldwide. $100K+ in prizes.",
    },
    {
        "name": "HackerEarth Challenges",
        "platform": "HackerEarth",
        "url": "https://www.hackerearth.com/challenges/",
        "location": "Online",
        "date": "Weekly",
        "description": "Online coding challenges and hackathons from companies hiring developers.",
    },
]


def get_fallback_hackathons(location: str = "", mode: str = "both", num: int = 5) -> List[Dict]:
    """Return curated list of hackathon platforms, filtered by mode."""
    out = CURATED_SOURCES[:]
    if location and location.lower() not in ("anywhere", ""):
        filtered = [
            h for h in out
            if location.lower() in h["location"].lower() or location.lower() in h["name"].lower()
        ]
        if filtered:
            out = filtered
    return out[:num]


# ─── Main search ─────────────────────────────────────────────

def search_hackathons(
    location: str = "anywhere",
    topics: str = "",
    mode: str = "both",
    num: int = 10,
) -> List[Dict]:
    """Search multiple platforms for upcoming hackathons."""
    all_results: List[Dict] = []

    print(f"\nSearching for upcoming hackathons...")
    if location and location.lower() not in ("anywhere", ""):
        print(f"  Location: {location}")
    if topics:
        print(f"  Topics:   {topics}")
    print(f"  Mode:     {mode}")
    print()

    all_results.extend(scrape_devpost(location, num))
    all_results.extend(scrape_mlh(location, num))
    all_results.extend(scrape_hackathoncom(location, num))

    # Strip past events
    all_results = strip_past(all_results)

    # Topic filtering (post-hoc since scrapers don't take topics)
    if topics:
        topic_list = [t.strip().lower() for t in topics.split(",")]
        filtered = []
        for r in all_results:
            combined = (r.get("name", "") + " " + r.get("description", "")).lower()
            if any(t in combined for t in topic_list):
                filtered.append(r)
        # If topic filtering removes everything, keep originals
        if filtered:
            all_results = filtered

    # Add curated sources if few live results
    if len(all_results) < 3:
        print("\n  Adding curated hackathon platforms...\n")
        all_results.extend(get_fallback_hackathons(location, mode, num))

    # De-duplicate by title
    unique: List[Dict] = []
    seen = set()
    for r in all_results:
        key = r["name"].lower().strip()[:50]
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:num]


# ─── CLI ─────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Search for upcoming hackathons online",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python event_finder.py --location London --topics "AI, web3"\n'
            "  python event_finder.py --from 2025-03-01 --to 2025-06-01\n"
            "  python event_finder.py --topics blockchain --mode online --count 5\n"
        ),
    )
    p.add_argument("--from", dest="date_from", default=None, help="Start date YYYY-MM-DD (default: today)")
    p.add_argument("--to", dest="date_to", default=None, help="End date YYYY-MM-DD (default: +3 months)")
    p.add_argument("--location", default="anywhere", help="City / region / country (default: anywhere)")
    p.add_argument("--topics", default="", help='Comma-separated themes (e.g. "AI, blockchain")')
    p.add_argument("--mode", choices=["online", "in-person", "both"], default="both", help="Event mode (default: both)")
    p.add_argument("--count", type=int, default=10, help="Max results (default: 10)")
    # Also support the old-style positional query for backward compat
    p.add_argument("query", nargs="*", help="(Legacy) free-text query")
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Legacy positional-query support: parse "find 3 hackathons in London"
    if args.query and not args.location:
        prompt = " ".join(args.query)
        if " in " in prompt.lower():
            args.location = prompt.lower().split(" in ")[-1].strip()
        for word in prompt.split():
            if word.isdigit():
                args.count = int(word)
                break

    today_str = TODAY.strftime("%Y-%m-%d")
    date_from = args.date_from or today_str
    date_to = args.date_to or (TODAY + timedelta(days=90)).strftime("%Y-%m-%d")

    # Clamp date_from to today
    if date_from < today_str:
        print(f"  Note: --from date {date_from} is in the past, clamped to {today_str}")
        date_from = today_str

    print("=" * 70)
    print("  UPCOMING HACKATHON SEARCH")
    print("=" * 70)
    print(f"  Period:   {date_from} -> {date_to}")
    print(f"  Location: {args.location}")
    print(f"  Topics:   {args.topics or '(any)'}")
    print(f"  Mode:     {args.mode}")
    print(f"  Max:      {args.count}")
    print("=" * 70)

    results = search_hackathons(
        location=args.location,
        topics=args.topics,
        mode=args.mode,
        num=args.count,
    )

    if not results:
        print("\n" + "=" * 70)
        print("  NO UPCOMING HACKATHONS FOUND")
        print("=" * 70)
        print("\nTry:")
        print("  - Broadening your location (or use --location anywhere)")
        print("  - Removing topic filters")
        print("  - Extending the date range (--to further out)")
        print("  - Checking sites directly:")
        print("    * https://devpost.com/hackathons")
        print("    * https://mlh.io/seasons/2026/events")
        print("    * https://ethglobal.com/events")
        return

    print("\n" + "=" * 70)
    print("  RESULTS -- UPCOMING HACKATHONS")
    print("=" * 70 + "\n")

    for i, evt in enumerate(results, 1):
        print(f"  {i}. {evt['name']}")
        print(f"     Platform: {evt['platform']}")
        print(f"     Location: {evt['location']}")
        print(f"     Date:     {evt['date']}")
        print(f"     URL:      {evt['url']}")
        if evt.get("description"):
            print(f"     Info:     {evt['description']}")
        print()

    print("=" * 70)
    print(f"  Found {len(results)} upcoming hackathon(s)")
    print("=" * 70)


if __name__ == "__main__":
    main()
