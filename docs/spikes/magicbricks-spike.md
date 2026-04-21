# MagicBricks API Spike

## Goal
Determine if MagicBricks has a scrapeable API endpoint for rental listings.

## Steps

### 1. Open MagicBricks rental search in Chrome
```
https://www.magicbricks.com/flats-for-rent-in-Bangalore-pppfs
```
Or manually: magicbricks.com → Rent → Bangalore → 2-3 BHK → 30K-70K budget

### 2. Open DevTools → Network tab → filter XHR/Fetch

### 3. Record what happens:
- What endpoints are called on page load?
- What happens on scroll (infinite scroll pagination)?
- What endpoints are called when filters change?
- Is there a JSON API or is it server-rendered HTML?
- What headers are required?
- Does it need cookies?

### 4. Check for known API patterns
MagicBricks is known to use:
- Possible endpoint: `/api/` or similar
- Possible SSR with `__NEXT_DATA__` (if Next.js)
- Infinite scroll triggers XHR for next page

### 5. Test from Python
```python
import httpx
resp = httpx.get(ENDPOINT, params=PARAMS, headers=HEADERS)
print(resp.status_code)
print(resp.json())
```

### 6. Also check api.market
"The API Guy" has a paid NoBroker + MagicBricks API:
```
https://api.market/store/the-api-guy/nobroker-api
```
- GET /api/magicbricks/properties
- GET /api/magicbricks/localities
- Check pricing and response quality

### 7. Document
- Endpoint URL(s)
- Required params
- Required headers/cookies
- Response shape
- Listing fields available
- Pagination method
- Rate limits
- Whether it's worth building vs using paid API

## What we need from the response
Same as NoBroker:
- rent, deposit, sqft, bhk
- lat, lng
- society name, locality
- photos
- amenities
- owner name (MagicBricks sometimes shows this)

## Known challenges
- MagicBricks uses infinite scroll (harder than pagination)
- May have anti-bot protection (Cloudflare etc)
- HTML scraping is fragile — prefer finding JSON API
- GitHub scrapers for MB exist but are old and for other cities

## To run this spike
```bash
# In Claude Code with Chrome extension:
# 1. Navigate to magicbricks.com rental search
# 2. Intercept XHR calls on page load and scroll
# 3. Test endpoint from Python
```
