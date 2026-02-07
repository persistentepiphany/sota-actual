# Event Finder - Live Hackathon Scraper

## Overview

`event_finder.py` now **actually scrapes live hackathon data** from real sources including:

- ✅ **Devpost API** - Currently working! Returns real-time hackathon data
- 🔄 **MLH (Major League Hacking)** - Attempted scraping
- 🔄 **Hackathon.com** - Attempted scraping
- 📋 **Curated Fallback** - Top hackathon platforms when scraping yields few results

## Features

### Live Data Sources
- **Devpost API**: Fetches current open hackathons via `/api/hackathons` endpoint
- **Real-time dates**: Shows actual submission deadlines (e.g., "Feb 07 - 08, 2026")
- **Direct links**: Provides clickable URLs to each hackathon page
- **Smart filtering**: Can filter by location when specified

### Fallback Directory
When scraping returns limited results, provides curated list of major platforms:
- Devpost (hundreds of active hackathons)
- MLH Official Season (200+ annual events)
- Hackathon.com (global community events)
- AngelHack (40+ cities)
- HackerEarth (weekly online challenges)
- Junction (Europe's leading hackathon)
- ETHGlobal (Web3/blockchain)
- Google Cloud Hackathons

## Usage

```bash
# Find 5 hackathons anywhere
python3 event_finder.py "find 5 hackathons"

# Find 10 hackathons  
python3 event_finder.py "find 10 hackathons"

# Find hackathons in specific location
python3 event_finder.py "find hackathons in London"
python3 event_finder.py "find 3 hackathons in San Francisco"
```

## Example Output

```
🔍 Searching for hackathons: 'find 5 hackathons' in 'anywhere'...

🔍 Scraping Devpost...
   ✓ Found 5 hackathon(s) on Devpost
🔍 Scraping MLH...
   ✓ Found 0 hackathon(s) on MLH
🔍 Scraping Hackathon.com...
   ✓ Found 0 hackathon(s) on Hackathon.com

======================================================================
🎯 LIVE HACKATHON RESULTS
======================================================================

1. Plymhack International 2026
   🏢 Platform: Devpost
   📍 Location: Online
   📅 Date: Feb 07 - 08, 2026
   🔗 URL: https://plymhack-2026.devpost.com/
   📝 Hackathon on Devpost - visit URL for details

2. ProdCon 2026
   🏢 Platform: Devpost
   📍 Location: Online
   📅 Date: Feb 07 - 08, 2026
   🔗 URL: https://prodcon-2026.devpost.com/
   📝 Hackathon on Devpost - visit URL for details

...

======================================================================
✅ Found 5 live hackathon(s)
======================================================================
```

## Technical Details

### Data Sources

**Devpost** (Working ✅)
- Endpoint: `https://devpost.com/api/hackathons`
- Method: JSON API
- Parameters: `status[]=open`, `order_by=recently-added`
- Headers: Standard browser UA + AJAX headers
- Returns: Real-time hackathon listings with titles, URLs, dates, locations

**MLH** (In Progress 🔄)
- Attempted endpoints: `https://mlh.io/seasons/2025/events`, `https://mlh.io/seasons/2026/events`
- Challenge: Dynamic content loading (likely React/client-side rendering)
- Potential solution: Use Playwright for browser automation or find API endpoint

**Hackathon.com** (In Progress 🔄)
- Attempted endpoint: `https://www.hackathon.com/events`
- Challenge: Page structure detection
- Potential solution: Analyze page structure more thoroughly

### Dependencies

```python
requests>=2.31.0      # HTTP requests
beautifulsoup4>=4.12.0  # HTML parsing
```

Optional (for future enhancement):
```python
playwright>=1.40.0    # Browser automation for JS-heavy sites
```

## Future Enhancements

1. **Browser Automation**: Use Playwright to scrape MLH and Hackathon.com (JS-rendered content)
2. **More Sources**: Add Eventbrite, Luma, HackerEarth APIs
3. **Caching**: Cache results to reduce API calls
4. **Date Parsing**: Better date extraction and formatting
5. **Themes/Tags**: Extract hackathon themes (AI, Web3, Health, etc.)
6. **Prize Info**: Scrape prize pool amounts when available

## Testing

```bash
# Run tests
python3 event_finder.py "find 5 hackathons"
python3 event_finder.py "find hackathons in London"
python3 event_finder.py "find 10 hackathons"
```

## Limitations

- **Rate Limiting**: Devpost API may rate limit excessive requests
- **Dynamic Content**: Some sites require JavaScript execution (MLH)
- **Anti-Scraping**: Sites may block automated access
- **Data Freshness**: Depends on source update frequency

## License

Part of the SOTA project.
