# Housing.com API Spike

## Goal
Determine if Housing.com has a scrapeable API endpoint for rental listings, similar to NoBroker's `/api/v3/multi/property/RENT/filter`.

## Steps

### 1. Open Housing.com rental search in Chrome
```
https://housing.com/in/buy/search?f=eyJiYXNlIjpbeyJ0eXBlIjoiQ0lUWSIsInZhbHVlIjoiNDc0In1dLCJ0eXBlIjpbIkFQQVJUTUVOVCJdLCJiZWRyb29tcyI6WyIyIiwiMyJdLCJidWRnZXRfbWluIjozMDAwMCwiYnVkZ2V0X21heCI6NzAwMDB9
```
Or manually: housing.com → Rent → Bangalore → 2-3 BHK → 30K-70K

### 2. Open DevTools → Network tab → filter XHR/Fetch

### 3. Record what happens:
- What endpoints are called?
- What are the request headers?
- What params are sent?
- What does the response look like?
- Is it JSON? GraphQL? Server-rendered HTML?
- Does it need auth/cookies?
- How is pagination handled?

### 4. Test from Python
Try hitting the endpoint with httpx, same as NoBroker:
```python
import httpx
resp = httpx.get(ENDPOINT, params=PARAMS, headers=HEADERS)
print(resp.status_code)
print(resp.json())
```

### 5. Document
- Endpoint URL
- Required params
- Required headers/cookies
- Response shape
- Listing fields available
- Pagination method
- Rate limits observed

## What we need from the response
At minimum:
- rent, deposit, sqft, bhk
- lat, lng (for map)
- society name, locality
- photos
- amenities (power backup, parking, gated etc)

## To run this spike
```bash
# In Claude Code with Chrome extension:
# 1. Navigate to housing.com rental search
# 2. Intercept XHR calls
# 3. Test endpoint from Python
```
