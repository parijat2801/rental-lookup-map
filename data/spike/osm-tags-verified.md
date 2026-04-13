# OSM Tags for Bangalore — Verified 2026-04-13

## Namma Metro Stations
Metro stations are tagged with ALL of these:
- `railway=station`
- `station=subway`
- `subway=yes`
- `public_transport=station`
- `network=Namma Metro`
- `operator=Bangalore Metro Rail Corporation Limited`

**Best query strategy**: Use `network=Namma Metro` to get ONLY metro (not Indian Railways).
Alternatively: `station=subway` within Bangalore bbox.

## Indian Railways Stations (to exclude)
Regular rail stations have:
- `railway=station`
- `network=IR`
- `operator=SWR` (South Western Railway)
- NO `station=subway` tag
- NO `network=Namma Metro`

## Verified metro stations found in bbox (12.93-13.02, 77.55-77.65):
- Srirampura (SPRU)
- Swami Vivekananda Road (SVRD)
- Indiranagar (IDN)
- Halasuru (HLRU)
- Trinity (TTY)
- Mahatma Gandhi Road / MG Road (MAGR)
- Cubbon Park (CBPK)
- Dr. B. R. Ambedkar / Vidhana Soudha (VDSA)
- Sir M. Visvesvaraya / Central College (VSWA)

## Recommended Overpass query for metro
```
node["network"="Namma Metro"](12.90,77.50,13.05,77.70);
```

## For parks/green — need to verify tags too
Will use: `leisure=park`, `leisure=garden`, `landuse=recreation_ground`

## For water/lakes
Will use: `natural=water`, `water=lake`
