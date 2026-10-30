# 99acres API Contract

## Fetch order
1. **Apify** (`themineworks/99acres-scraper`) when `APIFY_TOKEN` is set —
   `python3 -m pip install 'rental-lookup[acres99-apify]'`. Items are adapted to
   the SRP shape below before saving under `data/raw_9a/`.
2. **JSON API** (optional browser `Cookie`) — often 401/403 behind Akamai.
3. **Chrome SSR** via Playwright reading `window.__initialData__.srp` —
   `python3 -m pip install 'rental-lookup[acres99]'`.

## Endpoint (legacy JSON API)
```
GET https://www.99acres.com/api-aggregator/srp/search
```
Formerly returned JSON. As of late 2026 this returns **401 Unauthorized Client**
(or Akamai 403) for non-browser clients without a fresh cookie.

## Query Parameters
| Param | Example | Notes |
|-------|---------|-------|
| `city` | `20` | Bangalore |
| `preference` | `R` | R=Rent, S=Sale |
| `res_com` | `R` | Residential |
| `area_unit` | `1` | sq.ft. |
| `property_type` | `1` | 1=Apartment / flat |
| `bedroom_num` | `1,2,3` | |
| `budget_min` | `0` | Monthly rent (rupees) for rent searches |
| `budget_max` | `150000` | |
| `page` | `1` | |
| `page_size` | `30` | |
| `platform` | `DESKTOP` | |
| `moduleName` | `GRAILS_SRP` | |
| `workflow` | `GRAILS_SRP` | |

## Response
```json
{
  "properties": [ ... ]   // mix of property tuples; skip items without PROP_ID
}
```

## Key Field Mapping (99acres → our field)
```
PROP_ID           → id (prefixed 9a_)
MIN_PRICE         → rent
SECURITY_DEPOSIT  → deposit (often absent on SRP)
AREA / BUILTUP_SQFT / CARPET_SQFT → sqft
BEDROOM_NUM       → bhk
SOCIETY_NAME / BUILDING_NAME / PROP_NAME → society
LOCALITY_WO_CITY / LOCALITY → locality
MAP_DETAILS.LATITUDE / LONGITUDE → lat, lng (labels sometimes swapped)
FLOOR_NUM         → floor
TOTAL_FLOOR       → total floors
FACING            → facing (numeric 1–8 or label)
FURNISH           → furnishing (1=FULL, 2=NONE, 4=SEMI)
AGE               → age_years
BALCONY_NUM       → balconies
GATED             → is_gated_community ("Y"/"N")
AMENITIES / FEATURES → amenity codes (comma-separated)
MEDIUM_PHOTO_URL / PHOTO_URL / PROPERTY_IMAGES → photos
PD_URL            → detail URL (relative)
PROP_HEADING      → title
POSTING_DATE      → daysAgo (epoch ms)
```

## Amenity codes used
```
1  power backup
3  lift
5  park
6  reserved parking
9  security
17 intercom
19 piped gas
21 pool
22 / 40 gym
23 club
26 visitor parking
39 fire safety
```

## Pagination
- Increment `page`; stop when `properties` has no PROP_ID items.
- ~30 results per page with `page_size=30`.

## Comparison with MagicBricks
- Similar SRP JSON shape; stronger bot protection (Akamai).
- Coordinates live under `MAP_DETAILS` and are occasionally label-swapped.
- City/locality centroids are common (`MAP_DETAILS.source` = CITY/LOCALITY).
