# MyGate Homes Spike

## Goal
Determine if MyGate Homes (MyGate's broker-free rent/sale marketplace for gated
communities) can be added as a listing source alongside NoBroker and MagicBricks.

## Findings (Oct 2026)

**Status: not feasible as an unauthenticated scraper. Left out of the pipeline.**

### No web listings
- `https://mygate.com/homes/` is a WordPress marketing page (Yoast, WooCommerce,
  `wp-content` plugins). It embeds no listing data and makes no listing XHR calls.
- The rest of `mygate.com` is marketing/blog content; `dashboard.mygate.com` is the
  society-admin login, not a listings portal.

### Share links are app-only
- Listings are shared as deep links, e.g.
  `https://mygate.com/dl/lib/?route=detail&content_id=HOM-68cd3d9820395e0012e9800d&content_type=HOM`
- On the web this returns a WordPress **404**; it only resolves inside the app.
- Listing ids look like `HOM-<24-hex Mongo ObjectId>`, which hints at the shape of
  the app's backend but isn't usable without it.

### Visibility is gated
- MyGate's FAQ: listings are "visible only to verified residents and trusted
  seekers"; contact happens in-app.
- Help article: listings are verified for 24–48 h before going live
  ([help.mygate.in](https://help.mygate.in/articles/128336-how-can-i-list-my-flat-or-villa-in-mygate-application)).
- Users outside MyGate societies report they can't browse listings at all
  ([r/bangalorerentals](https://www.reddit.com/r/bangalorerentals/comments/1noc9ay/anyone_in_gated_societies_please_check_if_there/)).

## If revisited: the app's private API (authenticated)
Capture what the Android/iOS app calls when browsing Homes:

1. Proxy the phone through Proxyman, HTTP Toolkit or mitmproxy and trust its CA.
   (The app may pin certificates; if so, this needs a rooted device / patched APK.)
2. Open Homes → Rent → filter to Bangalore, 2–3 BHK, budget.
3. Record:
   - endpoint host + path, method, query/body params
   - auth header (bearer token? session cookie?) and how long it lives
   - pagination (page/offset/cursor) and page size
   - response shape — check for the fields below
4. Replay from Python with `httpx`, same as `sources/magicbricks.py`.

Caveats: tied to one personal account, token refresh/expiry to handle, likely
against MyGate's terms, and could get the account flagged. Not suitable for the
GitHub Actions daily refresh without storing a personal token as a secret.

## What we'd need from the response
Same as NoBroker / MagicBricks:
- rent, deposit, maintenance, sqft, bhk
- lat, lng (or society name precise enough to geocode — every listing is in a
  known gated society, so society-level coordinates would be accurate)
- society name, locality
- photos
- amenities, furnishing, floor, facing
- posted date (for `daysAgo`)
