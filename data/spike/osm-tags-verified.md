# OSM Tags for Bangalore — Verified 2026-04-13

## Namma Metro Stations
Metro stations are tagged with ALL of these:
- `railway=station`
- `station=subway`
- `subway=yes`
- `public_transport=station`
- `network=Namma Metro`
- `operator=Bangalore Metro Rail Corporation Limited`

**Best query strategy**: Use `network=Namma Metro` to get ONLY metro (not Indian Railways). Alternatively: `station=subway` within Bangalore bbox.

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

## Tags the project actually uses
Defined in `OSM_FEATURE_TAGS` in `rental_lookup/location.py` (the bounding box there covers the NoBroker search anchors):

| Feature | Tags | Minimum area |
|---------|------|--------------|
| Parks | `leisure=park`, `leisure=nature_reserve` | 5,000 m² |
| Lakes | `water=lake` | 10,000 m² |
| Woods / tree cover | `natural=wood`, `landuse=forest` | 10,000 m² |
| Metro | `network=Namma Metro` | none (points) |

`leisure=garden`, `landuse=recreation_ground`, scrub, tree rows and orchards are deliberately left out: they are everywhere in Bangalore's OSM data and made every listing look leafy. Bump `OSM_CACHE_VERSION` when these change so cached GeoPackages are rebuilt.
