# Security policy

## Reporting a vulnerability

Please don't open a public issue for security problems. Instead, report them
privately through GitHub's
[private vulnerability reporting](https://github.com/sarweshshah/rental-map/security/advisories/new)
with steps to reproduce. We'll acknowledge the report as soon as we can.

## Scope

rental-map is a local tool, so the main areas of concern are:

- **The local map server** (`rental_lookup/webmap/server.py`), which writes POSTed
  star data to disk. It is meant for local use only; don't expose it to a network.
- **The generated map page**, which embeds scraped text. Scraped fields must be
  escaped before being inserted into HTML.
- **Secrets.** API keys (`CARTO_BASEMAPS_KEY`) belong in
  environment variables, a gitignored `.env`, or GitHub Actions secrets, never in
  committed files. Note that the CARTO key is embedded in the built map page, so use
  a key restricted to your Pages domain.
