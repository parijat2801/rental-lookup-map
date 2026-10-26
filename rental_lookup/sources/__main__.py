"""Fetch listings from one source, or all of them, into data/.

Run: rental-map-fetch SOURCE [--cookie COOKIE]
 or: python -m rental_lookup.sources SOURCE [--cookie COOKIE]

SOURCE is `nobroker`, `magicbricks`, `99acres`, `propertyangel` or `all`. Raw
result pages are saved under data/raw/ (NoBroker), data/raw_mb/ (MagicBricks),
data/raw_9a/ (99acres) and data/raw_pa/ (Property Angel) for the map builder.
NoBroker reuses neighbourhoods already saved in data/raw/; empty it for a fresh
fetch (scripts/refresh_map.sh does this, keeping the old pages in data/raw_prev/).
Property Angel reuses details saved in data/raw_pa/ and only fetches new properties.
"""
from __future__ import annotations

import argparse

from rental_lookup.models import Listing
from rental_lookup.paths import (
    ACRES99_PAGES_DIR, MAGICBRICKS_PAGES_DIR, NOBROKER_PAGES_DIR, PROPERTYANGEL_PAGES_DIR,
)
from rental_lookup.sources import acres99, magicbricks, nobroker, propertyangel


def fetch_nobroker(cookie: str = "") -> list[Listing]:
    return nobroker.fetch_all(cookie=cookie, pages_dir=NOBROKER_PAGES_DIR)


def fetch_magicbricks(cookie: str = "") -> list[Listing]:
    """`cookie` is accepted for a uniform interface; MagicBricks needs none."""
    return magicbricks.parse_listings(magicbricks.fetch_all(pages_dir=MAGICBRICKS_PAGES_DIR))


def fetch_acres99(cookie: str = "") -> list[Listing]:
    """`cookie` is a browser Cookie header; needed when Akamai blocks plain requests."""
    return acres99.parse_listings(acres99.fetch_all(pages_dir=ACRES99_PAGES_DIR, cookie=cookie))


def fetch_propertyangel(cookie: str = "") -> list[Listing]:
    """`cookie` is accepted for a uniform interface; Property Angel needs none."""
    return propertyangel.parse_listings(propertyangel.fetch_all(pages_dir=PROPERTYANGEL_PAGES_DIR))


SOURCES = {
    "nobroker": fetch_nobroker,
    "magicbricks": fetch_magicbricks,
    "99acres": fetch_acres99,
    "propertyangel": fetch_propertyangel,
}


def _print_summary(source: str, listings: list[Listing]) -> None:
    print(f"\n{source}: {len(listings)} listings")
    for listing in listings[:5]:
        print(f"  Rs.{listing.rent:,} | {listing.sqft}sqft | {listing.bhk} | {listing.society} | {listing.locality}")
        print(f"    {listing.url[:80]}")


def main(argv: list | None = None) -> None:
    parser = argparse.ArgumentParser(prog="rental-map-fetch", description="Fetch rental listings into data/.")
    parser.add_argument("source", choices=[*SOURCES, "all"], help="which listing source to fetch")
    parser.add_argument("--cookie", default="",
                        help="Cookie header for NoBroker / 99acres, only needed if requests get blocked")
    args = parser.parse_args(argv)

    for name in SOURCES if args.source == "all" else [args.source]:
        print(f"=== Fetching {name} ===")
        _print_summary(name, SOURCES[name](cookie=args.cookie))


if __name__ == "__main__":
    main()
