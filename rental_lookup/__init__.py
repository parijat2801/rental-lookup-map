"""Find and rank Bangalore rentals from NoBroker and MagicBricks.

Package layout:
    sources/       scrapers: nobroker, magicbricks, facebook (experimental)
    enrichment/    slow per-listing extras: listing_details
    webmap/        builder (data -> output/map.html), template.html, server, dev watcher
    models.py      the normalised `Listing` and related dataclasses
    location.py    OpenStreetMap parks/lakes/metro/woods and distance lookups
    scoring.py     CLI suitability score; ranking_report.py writes results.csv
    listing_age.py how many days ago a listing was posted
    stars.py       merging starred/dismissed listings across copies
    paths.py       every data/output location in one place
"""
