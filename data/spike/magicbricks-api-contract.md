# MagicBricks API Contract (verified 2026-04-21)

## Endpoint
```
GET https://www.magicbricks.com/mbsrp/propertySearch.html
```
Returns JSON directly! No auth/cookies needed.

## Query Parameters
| Param | Example | Notes |
|-------|---------|-------|
| `editSearch` | `Y` | Required |
| `category` | `R` | R=Rent |
| `propertyType` | `10002,10003,10021,10022` | 10002=Apartment, 10003=Builder Floor |
| `bedrooms` | `2,3` | |
| `cityName` | `Bangalore` | |
| `budgetMin` | `30000` | |
| `budgetMax` | `70000` | |
| `page` | `1` | |

## Response
```json
{
  "resultList": [...],           // 30 per page
  "editAdditionalDataBean": {},  // pagination/filter metadata
  "nsrResultList": [...],        // nearby results
}
```

## Key Field Mapping (MB field → our field)
```
price           → rent (number)
bookingAmtExact → deposit (number)
carpetArea      → sqft (number)
coveredArea     → covered sqft
bedroomD        → bhk ("3")
prjname         → society/project name
lmtDName        → locality name (e.g. "Rajajinagar")
ctName          → city ("Bangalore")
pmtLat          → latitude
pmtLong         → longitude
floorNo         → floor
floors          → total floors
facingD         → facing ("East")
furnishedD      → furnishing ("Semi-Furnished")
acD             → property age ("5 to 10 years")
allImgPath      → array of photo URLs
image           → thumbnail URL
imgCt           → photo count
url             → detail URL (relative)
maintenanceCharges → maintenance (number)
maintenanceD    → "Monthly"
parkingD        → "2 Covered"
balconiesD      → "3"
bathD           → "3"
powerStatusD    → "No/Rare Powercut"
waterStatus     → "Water Availability 24 Hours Available"
bachelor        → "Y" if bachelors allowed
possStatusD     → "Immediately"
oname           → owner/agent name
contName        → contact name
userType        → "Agent" or "Owner"
amenities       → space-separated codes
landmark        → nearby landmarks
propertyTitle   → full title
```

## Photos
- `allImgPath`: Array of full photo URLs (cropped, h470_w1080)
- `image`: Single thumbnail (h180_w240)
- `imgCt`: Total photo count

## Pagination
- 30 results per page
- Increment `page` param

## No auth needed
Works with just User-Agent and Accept headers. No cookies required.

## Comparison with NoBroker
- MB has 211 fields vs NoBroker's ~98
- MB includes maintenance amount directly
- MB has owner/agent name visible
- MB has property age as text ("5 to 10 years") vs NoBroker's number
- MB amenities are code-based (12201 etc) vs NoBroker's boolean map
- MB has landmark data
- MB has RERA info for agents
