# NoBroker API Contract (verified 2026-04-13)

## Endpoint
```
GET https://www.nobroker.in/api/v3/multi/property/RENT/filter
```

## Query Parameters
| Param | Example | Notes |
|-------|---------|-------|
| `city` | `bangalore` | lowercase |
| `pageNo` | `1` | 1-indexed, 26 results per page |
| `searchParam` | base64-encoded JSON | see below |
| `rent` | `0,60000` | min,max in INR |
| `type` | `BHK2,BHK3` | comma-separated |

## searchParam format
Base64-encoded JSON array of location objects:
```json
[{"lat":12.9716,"lon":77.6412,"placeId":"ChIJbTDDCWAXujYRZyFs0FD4KFI","placeName":"Indiranagar"}]
```

## Headers
- Request made from browser context with cookies (credentials: include)
- Standard browser User-Agent
- No special auth headers observed

## Response shape
```json
{
  "status": "success",
  "data": [ ... ],       // array of listings, 26 per page
  "otherParams": { ... } // includes totalCount
}
```

## Listing fields (verified from real response)
```
rent: 45000              (number, INR/month)
deposit: 250000          (number, INR)
propertySize: 1100       (number, sqft)
type: "BHK2"             (string enum: BHK1, BHK2, BHK3, BHK4)
typeDesc: "2 BHK"        (human readable)
furnishingDesc: "Semi"   (string: "Semi", "Full", "Not")
parking: "TWO_WHEELER"   (string enum: TWO_WHEELER, FOUR_WHEELER, BOTH, NONE)
parkingDesc: "Bike"      (human readable)
latitude: 12.9718        (float)
longitude: 77.6411       (float)
locality: "Indiranagar, Bengaluru, Karnataka, India"
society: "Independent House"  (society/building name or "Independent House")
buildingType: "IH"       (string enum: IH=independent house, AP=apartment)
floor: 1                 (number)
totalFloor: 1            (number)
lift: false              (boolean)
bathroom: 2              (number)
facing: "E"              (string: N, S, E, W, NE, NW, SE, SW)
waterSupply: "CORPORATION" (string enum)
leaseType: "FAMILY"      (string enum: FAMILY, BACHELOR, COMPANY, ANY)
propertyAge: 5           (number, years)
propertyTitle: "2 BHK House for Rent..."
detailUrl: "/property/..."
id: "ff808181..."        (hex string, unique)
activationDate: ...
maintenanceIncluded: false
formattedMaintenanceAmount: ""
amenitiesMap: {           (object, boolean flags)
  "LIFT": false,
  "GYM": false,
  "INTERNET": false,
  "AC": false,
  "CLUB": false,
  "INTERCOM": false,
  "POOL": false,
  "CPA": false,          // covered parking area
  "FS": false,           // fire safety
  "SERVANT": false,
  "SECURITY": false,
  "SC": false,           // shopping center
  "GP": false,           // gated community / guarded premises
  "PARK": false,         // park
  "RWH": false,          // rainwater harvesting
  "STP": false,          // sewage treatment
  "HK": false,           // housekeeping
  "PB": false,           // power backup
  "VP": false            // visitor parking
}
```

## Key findings
- `amenitiesMap.PB` = power backup (boolean)
- `amenitiesMap.GP` = gated premises / gated community (boolean)
- `amenitiesMap.CPA` = covered parking area (boolean)
- `amenitiesMap.SECURITY` = security guard (boolean)
- `parking` field has car/bike enum, `amenitiesMap.CPA` is covered parking
- `society` field distinguishes gated communities from independent houses
- `leaseType` can filter FAMILY vs BACHELOR
- No explicit "pet friendly" field — must scan propertyTitle/description
- `description` was null in sample — may need detail page fetch for full text
- Page size is 26 listings
- Pagination: increment pageNo until data array is empty
