# Property Angel API Contract

Derived from `rental_lookup/sources/propertyangel.py`. JSON, no auth, but requests must carry the site's `Origin` and `Referer` (`https://www.propertyangel.in`).

## Endpoints
```
GET https://pa-api-core-509395667802.us-central1.run.app/properties/all
GET https://pa-api-core-509395667802.us-central1.run.app/properties/detail/{PropID}
```

- `/properties/all` returns every marketed property in `data[]`, each with its fields under `meta_data`. Summary fields only, **no coordinates**. The scraper keeps entries whose `City_Zone_Classification.City` is `Bangalore`.
- `/properties/detail/{PropID}` returns one property in full under `data`, including `LatLong`.
- The scraper merges the two (`{**detail, **summary}`), so fresh summary fields (rent, furnishing, tenancy...) override older saved details.

## Rate limit
100 requests per 15 minutes per IP, and the site's own property pages spend the same quota (one detail request per page view).

- Detail payloads are saved one per property as `data/raw_pa/propertyangel_<PropID>.json` and reused on later runs.
- At most `MAX_NEW_DETAILS_PER_RUN` (60) new details are fetched per run, with a 1 s pause between them; the rest wait for the next run.
- HTTP 429 stops further detail fetches for the run; failed details are not retried.
- Saved properties that are no longer marketed are deleted.

## Key Field Mapping (Property Angel → our field)
```
PropID.display_value                       → id (prefixed pa_)
Advertised_Rent                            → rent
Advertised_Security_Deposit                → deposit
Association_maintenance_amount             → maintenance (0 when Advertised_Rent_Includes_Mnt says "included")
Built_Up_Area_sft                          → sqft
No_of_Bedrooms                             → bhk ("BHK<n>")
LatLong.latitude / longitude               → lat, lng (fallback: Latitude_New / Longitude_New)
Projects.display_value                     → society (falls back to locality)
Location_Area.display_value                → locality
Property_Type                              → building type (Apartment/Duplex/Villament → AP,
                                             Building Unit → IF, Independent House → IH, Villa → GC)
Unit_is_on_Floor_0_for_Ground_floor        → floor
Total_no_of_Floors                         → total floors
Main_door_facing_Direction                 → facing
Furnishing                                 → furnishing (FULL / SEMI / NONE, "" if unknown)
No_of_Covered_Car_Parks / No_of_Open_Car_Parks → parking (any car park → FOUR_WHEELER)
No_of_Balconies                            → balconies (-1 when absent)
Projects.Security / Projects.Power_backup  → has_security / has_power_backup
ImageList[].image                          → photos (primary first; resized via imop=Resize,width=800;Convert,format=webp)
```

Zoho-style lookup fields arrive as `{"ID": ..., "display_value": ...}`.

## Not published
- **Lift**: inferred as an apartment with 5+ floors (Bangalore bylaws require a lift above ground + 4 floors).
- **Property age, water supply, negotiability, fire safety**: absent; the map treats age as unknown (`age_years = 99`).
- **Posted date**: not published; listing age is the number of days since we first saw the listing (`data/cache/first_seen.json`).

## Listing URL
`https://www.propertyangel.in/property/<slug>-papid-<PropID>`. The site only reads the trailing `papid-<PropID>`; the slug is built from the title.
