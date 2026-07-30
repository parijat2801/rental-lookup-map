# Rental Lookup — OSS Launch Plan

*Status: design agreed, not started. Current private repo stays private; this describes a new public one.*

## What this is

A local-first rental search tool. Scrapes listing portals directly, dedupes across
them, scores results, and shows everything on one map with real filters. Built
because searching for a flat means tabbing between four portals with bad UI, each
one optimising for the broker rather than the renter.

Currently Bangalore-only, NoBroker + MagicBricks.

## What we are and are not promising

**Not promising:** uptime, support, updates, or that it will work next month. The
scrapers hit undocumented internal APIs. Those change without notice and the tool
breaks until someone fixes it. That someone is whoever cares, not necessarily the
author.

**Promising:** the code works today, it's yours to modify, and your data stays on
your machine.

This is deliberate. Every alternative — hosted service, paid tier, maintained
desktop app — converts a hobby project into an obligation, and adds legal exposure
that a free tool distributed as source does not carry. Users who can run a Python
script can also read a traceback and patch a selector. That's the audience.

## Architecture

**Local-first.** All listing data and personal state (stars, dismissals) live in
local files. The app is fully functional with no network beyond the scrape itself.

**Scraper plugins.** Each source is one file exposing `fetch()` (yields raw
records) and `normalize()` (raw record → `Listing`). Sources declare a drive mode:
`per_area` (seeded by locality coordinates, paginate until empty — how NoBroker
works) or `city_wide` (single query, page cap — how MagicBricks works). Do not
force one into the other; the split is the difference between adding a scraper in
an afternoon and fighting the framework.

**Small required field set.** `id, url, rent, sqft, bhk, lat, lng, locality` are
required. Everything else is optional with defaults. The current model has 34
required fields including NoBroker-specific scores (`nb_transit`, `nb_lifestyle`),
which would force a new scraper's author to invent values. Fix this before
publishing.

**Loud validation at the normalize boundary.** Reject bad records with a message
naming the field, rather than silently dropping them. The common failure for a new
scraper is a wrong field mapping producing plausible-but-empty listings, and
silent drops make that invisible.

**Everything downstream is source-agnostic:** dedup, scoring, map. Adding a
scraper should require zero changes outside its own file plus one registry line.

## Distribution

Repo first. A Tauri wrapper with an auto-update channel is a maybe-later, not a
v1 — packaging reaches non-technical users, who are exactly the people stranded
when a scraper breaks and nobody's fixing it. Ship to the audience the no-support
model actually serves.

Sequencing: publish repo → see if anyone uses it → build the wrapper only if
there's pull. Building distribution for untested demand is the expensive mistake.

## Sync (v2, not v1)

**v1 has no sync.** Local JSON file. Sharing is "send someone your stars.json".
For a coder audience this is an acceptable answer and costs nothing.

**v2, if wanted:** auto-generated share code addressing a blob on one Cloudflare
Worker + KV. No accounts, no setup, works out of the box.

Non-negotiable properties:

- **Local is authoritative.** Sync failure is a silent no-op, never an error. The
  current CI does the opposite — it hard-fails with `Refusing to publish empty
  stars` — and that behaviour must not carry over.
- **Endpoint is a config value**, so the backend can be swapped without a rewrite.
- **Shared stars stay in a separate layer**, not merged into yours. Yours render
  one colour, theirs another. Whose judgment a star represents *is* the value —
  merging flattens it into an anonymous star and can't be undone. (Consider a ring
  or badge rather than fill colour, since fill already encodes score.)

**Failure messaging** should distinguish causes: over capacity → say so; author
moved on → say that and point at self-hosting via a Gist. Default to "sharing
unavailable, your stars are safe locally" for transient failures, so a blip
doesn't read as abandonment.

### Rejected sync approaches, and why

Recorded so they don't get re-litigated:

- **True P2P / WebRTC** — two peers behind home NAT can't connect without
  signalling plus a TURN relay when hole-punching fails. TURN costs bandwidth.
  Also requires both apps open simultaneously, which doesn't match usage (people
  browse at different times).
- **BitTorrent** — distributes large immutable files. This is small mutable state.
  Mutable DHT entries are ~1KB, expire in hours, and are keyed to one signer.
- **IPFS** — content-addressed, so every change is a new CID. IPNS is slow and
  single-signer. Nothing persists unless a node pins it, so you need a pinning
  service, which is the hosted thing being avoided.
- **CRDT** — overkill. Star/dismiss is already last-write-wins with tombstones,
  and genuine conflicts are near-impossible in a two-person hunt.
- **Dropbox / Drive folder** — actually the best answer for two known people, but
  "set up a shared folder first" is a setup step that kills a consumer app.

The general shape: every serverless-P2P option gives up mutability, availability
when peers are offline, or NAT traversal. Small mutable state, two people, never
both online, no infrastructure is not a solved combination. For a few kilobytes, a
key-value store is the correct engineering answer, not a compromise.

## Extending it with an agent

Ship a `CLAUDE.md` and `EXTENDING.md` describing the scraper contract, a heavily
commented example scraper, and a validation command (`validate scrapers/foo.py`)
that reports listings fetched, missing coordinates, and type mismatches.

The validation loop is the whole thing. An agent writing a scraper against an
undocumented API *will* get mappings wrong; a validator that says "12 fetched, 3
missing coords, rent is a string" lets it self-correct. Without it, the agent
produces plausible code that yields garbage.

Also document *how the endpoint was found* (devtools, watching XHR), not just what
it is. Discovery is the step most likely to fail, and it's the transferable part.

Caveat: this raises the docs quality bar rather than lowering it. Every ambiguity
in the contract becomes an agent failure mode landing on a user with no
maintainer.

## Before publishing — cleanup checklist

- [ ] **Strip personal data.** `data/cache/stars_and_dismissals.json` contains 49
      starred and 1,882 dismissed listings — a personal house-hunting history that
      would ship as every new user's default state. Same for `photo_ratings.json`.
- [ ] **Drop the embedded data blob.** `output/map_template.html` carries ~2.9MB of
      live listings that `build_map.py` splices via `var ALL = `. Anyone cloning
      gets that baked in, and every rebuild churns a huge diff. Template-as-database
      needs replacing or at minimum documenting.
- [ ] **Widen the BHK query.** `nobroker.py` requests only `BHK2,BHK3`, so 1BHK and
      4BHK don't exist in the data. Fine personally, limiting for others.
- [ ] **Move city config to one file.** `NEIGHBORHOODS` (nobroker.py), `BBOX`
      (geo.py), and the scoring weights (template JS) are in three places. Someone
      adding a city has to find all three — this is the highest-leverage change for
      getting contributions.
- [ ] **Pick a license.** MIT matches "take it and enjoy". AGPL if it matters that
      modified hosted versions publish changes.
- [ ] Verified clean already: no hardcoded credentials in any Python/YAML/shell file.

## Known gaps in the tool itself

- **Furnishing is not scraped** from either source. It's a top-three filter on
  every rental portal. Needs a scraper change, not a UI change. Highest-value
  missing feature for strangers.
- **Availability date** is scraped but populated on only 1,931 of 8,983 listings —
  too sparse for a hard filter, better as a sort or badge.
- **Metro proximity scoring is wrong east of lon 77.70.** `geo.py` `BBOX` clips the
  OSM fetch, so eastern listings compute `nearest_metro_m = None` and rank as
  transit-less despite being walking distance from Purple Line stations. Coverage
  was fixed; scoring wasn't.
- **`photo_rater.py` is dead code.** Never invoked by CI, so ratings are frozen at
  132 of ~9,000 listings. Either wire it into the pipeline or delete it along with
  the cached ratings.
- **Data sentinels:** `age: 99` (957 listings) and `age: -1` (54) are nulls in
  disguise and would break a naive max-age filter. `facing` is empty on 42% of
  listings, so facing-based filters silently keep unknowns.
- **Cross-source dedup is tuned for NoBroker↔MagicBricks specifically** (BHK match,
  rent ±15%, sqft ±15%, locality substring). With more scrapers of varying quality
  this heuristic gets shakier and a bad scraper degrades results for everyone.
  Consider making it configurable or disableable per source pair.

## Legal position

The scrapers hit undocumented internal APIs. Their terms of service could not be
verified — NoBroker's terms URL 302s to a 404, MagicBricks blocks automated
fetching, and search returned only third-party commentary (much of it from
companies selling scrapers, i.e. not neutral). **Assume automated access is
prohibited by both.**

Risk differs sharply by model:

- **Distributing source, users self-host** — low risk, well-trodden. Each user
  scrapes from their own IP; you're distributing software, not reselling data.
- **Hosting a service or charging for access** — materially different exposure.
  That's a lawyer question, not one to resolve by reasoning about it.

Practical fragility matters more than legal risk at this scale: an undocumented
endpoint hit daily from GitHub Actions IP ranges can be blocked with a Cloudflare
rule in an afternoon. Free-and-unsupported absorbs that; a paid product does not.

## Explicitly out of scope

Multi-city, accounts, merged stars, true P2P, hosted service, payments, packaged
binary for non-technical users. Each was considered and rejected above — revisit
only with a specific reason, not by default.
