"""Find and rank Bangalore rentals from NoBroker, MagicBricks, 99acres and Property Angel.

Package layout:
    sources/       scrapers: nobroker, magicbricks, acres99, propertyangel, facebook (experimental)
    enrichment/    slow per-listing extras: listing_details
    webmap/        builder (data -> output/map.html), template.html + ui/, server, dev watcher
    models.py      the normalised `Listing` and related dataclasses
    location.py    OpenStreetMap parks/lakes/metro/woods and distance lookups
    scoring.py     CLI suitability score; ranking_report.py writes results.csv
    listing_age.py how many days ago a listing was posted
    stars.py       merging starred/dismissed listings across copies
    paths.py       every data/output location in one place
"""
