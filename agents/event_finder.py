#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
event_finder.py -- Search for hackathons, conferences, and events

Usage:
    python3 event_finder.py "find 3 hackathons in London"
    python3 event_finder.py "AI conferences in Berlin"
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
import re
from typing import List, Dict
import xml.etree.ElementTree as ET

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


def scrape_devpost(location="", num=10) -> List[Dict]:
    """Scrape live hackathons from Devpost using their JSON API"""
    results = []
    try:
        print("🔍 Scraping Devpost...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        # Try Devpost's API endpoint for hackathons
        url = "https://devpost.com/api/hackathons"
        params = {'status[]': 'open', 'order_by': 'recently-added'}
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            try:
                data = response.json()
                hackathons = data.get('hackathons', [])
                
                for hack in hackathons[:num]:
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
                        
                        # Filter by location if specified
                        if location and location.lower() not in loc_text.lower() and location.lower() not in title.lower():
                            continue
                        
                        results.append({
                            "name": title,
                            "platform": "Devpost",
                            "url": link,
                            "location": loc_text,
                            "date": date_text,
                            "description": desc_text or "Hackathon on Devpost - visit URL for details"
                        })
                    except Exception as e:
                        continue
            except json.JSONDecodeError:
                pass
                    
        print(f"   ✓ Found {len(results)} hackathon(s) on Devpost")
    except Exception as e:
        print(f"   ⚠️  Devpost error: {e}")
    
    return results


def scrape_mlh(location="", num=10) -> List[Dict]:
    """Scrape live hackathons from Major League Hacking (MLH)"""
    results = []
    try:
        print("🔍 Scraping MLH...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # MLH events page - try both 2025 and 2026
        for year in ["2026", "2025"]:
            url = f"https://mlh.io/seasons/{year}/events"
            try:
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Try multiple selectors
                    events = (
                        soup.find_all('div', class_='event') or
                        soup.find_all('div', class_=re.compile(r'event.*card', re.I)) or
                        soup.select('.event-wrapper .event') or
                        soup.find_all('a', href=re.compile(r'/event/'))
                    )
                    
                    for event in events[:num]:
                        try:
                            # Find title
                            title_elem = (
                                event.find('h3') or 
                                event.find('h2') or 
                                event.find('a', href=True) or
                                event.find(class_=re.compile(r'.*title.*', re.I))
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
                            
                            # Extract location
                            loc_text = "Online"
                            loc_elem = event.find(class_=re.compile(r'.*location.*', re.I))
                            if loc_elem:
                                loc_text = loc_elem.get_text(strip=True)
                            
                            # Filter by location if specified
                            if location and location.lower() not in loc_text.lower() and location.lower() not in title.lower():
                                continue
                            
                            results.append({
                                "name": title,
                                "platform": "MLH",
                                "url": link or url,
                                "location": loc_text,
                                "date": date_text or "Check website for dates",
                                "description": "Official MLH hackathon"
                            })
                        except Exception as e:
                            continue
                    
                    if results:
                        break
            except Exception:
                continue
        
        print(f"   ✓ Found {len(results)} hackathon(s) on MLH")
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
                    link_elem = event.find('a', href=True)
                    if link_elem and 'href' in link_elem.attrs:
                        link = link_elem['href']
                        if link and not link.startswith('http'):
                            link = f"https://www.hackathon.com{link}"
                    
                    # Extract any text that looks like a date
                    date_text = ""
                    text = event.get_text()
                    date_patterns = [
                        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:\s*-\s*\d{1,2})?,?\s+\d{4}\b',
                        r'\b\d{1,2}/\d{1,2}/\d{4}\b',
                        r'\b\d{4}-\d{2}-\d{2}\b'
                    ]
                    for pattern in date_patterns:
                        match = re.search(pattern, text, re.I)
                        if match:
                            date_text = match.group()
                            break
                    
                    loc_text = "Online"
                    if "online" in text.lower() or "virtual" in text.lower():
                        loc_text = "Online"
                    elif location:
                        loc_text = location
                    
                    # Filter by location if specified
                    if location and location.lower() not in loc_text.lower() and location.lower() not in title.lower():
                        continue
                    
                    results.append({
                        "name": title,
                        "platform": "Hackathon.com",
                        "url": link or url,
                        "location": loc_text,
                        "date": date_text or "Check website for dates",
                        "description": "Community hackathon"
                    })
                except Exception as e:
                    continue
        
        print(f"   ✓ Found {len(results)} hackathon(s) on Hackathon.com")
    except Exception as e:
        print(f"   ⚠️  Hackathon.com error: {e}")
    
    return results


def get_fallback_hackathons(location="", num=5) -> List[Dict]:
    """Return curated list of real hackathon platforms and current events"""
    # These are real, currently active hackathon platforms
    fallback_results = [
        {
            "name": "Explore Devpost - Live Hackathons",
            "platform": "Devpost",
            "url": "https://devpost.com/hackathons",
            "location": "Online & Worldwide",
            "date": "Year-round",
            "description": "Browse hundreds of active hackathons on Devpost. Filter by theme, prize, location, and dates. Join challenges from top companies like Google, Microsoft, and startups."
        },
        {
            "name": "MLH Official Hackathon Season 2025-2026",
            "platform": "MLH",
            "url": "https://mlh.io/seasons/2026/events",
            "location": "Online & Worldwide",
            "date": "Sep 2025 - Aug 2026",
            "description": "Major League Hacking hosts 200+ official student hackathons annually. Free swag, mentorship, workshops, and prizes for students worldwide."
        },
        {
            "name": "Hackathon.com Global Events",
            "platform": "Hackathon.com",
            "url": "https://www.hackathon.com/events",
            "location": "Worldwide",
            "date": "Updated Daily",
            "description": "Community-driven hackathon discovery platform with events from around the world. Filter by location, theme, and skill level."
        },
        {
            "name": "AngelHack Global Hackathon Series",
            "platform": "AngelHack",
            "url": "https://angelhack.com/events/",
            "location": "40+ Cities Globally",
            "date": "Year-round",
            "description": "One of the world's largest hackathon organizers with events in major cities. Focus on innovation, startups, and emerging tech."
        },
        {
            "name": "HackerEarth Challenges",
            "platform": "HackerEarth",
            "url": "https://www.hackerearth.com/challenges/",
            "location": "Online",
            "date": "Weekly",
            "description": "Online coding challenges and hackathons from companies hiring developers. Compete for prizes and job opportunities."
        },
        {
            "name": "Junction Hackathon (Europe's Leading)",
            "platform": "Junction",
            "url": "https://www.junction.fi/",
            "location": "Helsinki, Finland + Online",
            "date": "November annually",
            "description": "Europe's leading hackathon with 1500+ participants. Annual flagship event plus online challenges throughout the year."
        },
        {
            "name": "ETHGlobal (Web3/Blockchain)",
            "platform": "ETHGlobal",
            "url": "https://ethglobal.com/events",
            "location": "Global cities + Online",
            "date": "Monthly",
            "description": "Premier Ethereum and Web3 hackathons worldwide. $100K+ in prizes, mentorship from blockchain experts."
        },
        {
            "name": "Google Cloud Hackathons",
            "platform": "Google",
            "url": "https://cloud.google.com/developers/hackathons",
            "location": "Online & Hybrid",
            "date": "Quarterly",
            "description": "Build with Google Cloud Platform, AI/ML APIs. Access to Google mentors and cloud credits."
        }
    ]
    
    # Filter by location if specified
    if location:
        filtered = [h for h in fallback_results if location.lower() in h['location'].lower() or location.lower() in h['name'].lower()]
        if filtered:
            return filtered[:num]
    
    return fallback_results[:num]


def search_hackathons(query, location="", num=5):
    """Search multiple platforms for live hackathons"""
    all_results = []
    
    print(f"🔍 Searching for hackathons: '{query}' in '{location or 'anywhere'}'...\n")
    
    # Scrape from multiple sources
    all_results.extend(scrape_devpost(location, num))
    all_results.extend(scrape_mlh(location, num))
    all_results.extend(scrape_hackathoncom(location, num))
    
    # If we didn't get many results from scraping, add curated sources
    if len(all_results) < 3:
        print("\n💡 Adding curated hackathon platforms...\n")
        all_results.extend(get_fallback_hackathons(location, num))
    
    # Remove duplicates based on name similarity
    unique_results = []
    seen_titles = set()
    
    for result in all_results:
        title_key = result['name'].lower().strip()[:50]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_results.append(result)
    
    return unique_results[:num]


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 event_finder.py \"find 3 hackathons in London\"")
        sys.exit(1)
    
    prompt = " ".join(sys.argv[1:])
    
    # Simple parsing
    if "hackathon" in prompt.lower():
        location = ""
        if " in " in prompt.lower():
            location = prompt.lower().split(" in ")[-1].strip()
        
        num = 5
        for word in prompt.split():
            if word.isdigit():
                num = int(word)
                break
        
        results = search_hackathons(prompt, location, num)
        
        if not results:
            print("=" * 70)
            print("⚠️  NO RESULTS FOUND")
            print("=" * 70)
            print("\n💡 Try:")
            print("   - Removing location filter")
            print("   - Checking your internet connection")
            print("   - Visiting sites directly:")
            print("     • https://devpost.com/hackathons")
            print("     • https://mlh.io/seasons/2025/events")
            print("     • https://www.hackathon.com/events")
            return
        
        print("\n" + "=" * 70)
        print("🎯 LIVE HACKATHON RESULTS")
        print("=" * 70 + "\n")
        
        for i, event in enumerate(results, 1):
            print(f"{i}. {event['name']}")
            print(f"   🏢 Platform: {event['platform']}")
            print(f"   📍 Location: {event['location']}")
            print(f"   📅 Date: {event['date']}")
            print(f"   🔗 URL: {event['url']}")
            if event.get('description'):
                print(f"   📝 {event['description']}")
            print()
        
        print("=" * 70)
        print(f"\n✅ Found {len(results)} live hackathon(s)")
        print("=" * 70)
    else:
        print("For job searches, use: python3 job_finder.py \"{}\"".format(prompt))


if __name__ == "__main__":
    main()
