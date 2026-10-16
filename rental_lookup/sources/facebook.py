"""Facebook "Flat & Flatmates" group scraper (experimental; not part of the map pipeline).

Requires the optional dependency:  pip install -e '.[facebook]'
Usage:                              python -m rental_lookup.sources.facebook cookies.txt

To get cookies.txt: install the "Get cookies.txt LOCALLY" Chrome extension, open
facebook.com while logged in, then export as a Netscape cookie file.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

from rental_lookup.paths import FACEBOOK_POSTS_DIR

GROUPS = {
    "flat-and-flatmates-bangalore": "344060792364300",
}
RENT_BUDGET = (25000, 70000)

# Tried in order; the first pattern that yields a plausible amount wins.
RENT_PATTERNS = [re.compile(p) for p in (
    r'(?:rent|rental|price|cost|amount)\s*[:\-]?\s*(?:rs\.?|inr|₹)\s*([\d,]+)',
    r'(?:rs\.?|inr|₹)\s*([\d,]+)\s*(?:/\s*(?:month|mon|pm|per month))',
    r'(?:rs\.?|inr|₹)\s*([\d,]+)',
    r'([\d,]+)\s*(?:rs|inr|₹)',
    r'([\d]+k)\s*(?:rent|pm|per month)',
)]
PLAUSIBLE_RENT_RANGE = (5000, 200000)
BHK_PATTERN = re.compile(r'(\d)\s*bhk', re.IGNORECASE)
AREA_PATTERN = re.compile(r'(\d[\d,]*)\s*(?:sq\.?\s*ft|sqft|sft|square\s*feet)', re.IGNORECASE)
PHONE_PATTERNS = [re.compile(p) for p in (
    r'(?:\+91[\s-]?)?[6-9]\d{9}',
    r'(?:\+91[\s-]?)?\d{5}[\s-]?\d{5}',
)]

LOCALITIES = [
    'indiranagar', 'koramangala', 'hsr', 'btm', 'jayanagar', 'jp nagar',
    'malleshwaram', 'rajajinagar', 'whitefield', 'marathahalli', 'domlur',
    'frazer town', 'ulsoor', 'halasuru', 'richmond', 'basavanagudi',
    'sadashivanagar', 'wilson garden', 'shivajinagar', 'banashankari',
    'electronic city', 'kr puram', 'bellandur', 'sarjapur', 'hebbal',
    'hennur', 'kalyan nagar', 'kammanahalli', 'benson town', 'cox town',
    'mg road', 'brigade road', 'lavelle', 'cunningham', 'vasanth nagar',
    'bommanahalli', 'bannerghatta', 'uttarahalli', 'padmanabhanagar',
]


def extract_rent(text: str) -> Optional[int]:
    """Monthly rent from free text, e.g. 'Rent: Rs. 45,000' or '45k pm'."""
    text = text.lower()
    for pattern in RENT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        amount = match.group(1).replace(',', '')
        if amount.endswith('k'):
            return int(float(amount[:-1]) * 1000)
        low, high = PLAUSIBLE_RENT_RANGE
        if amount.isdigit() and low <= int(amount) <= high:
            return int(amount)
    return None


def extract_bhk(text: str) -> Optional[str]:
    match = BHK_PATTERN.search(text)
    return f"BHK{match.group(1)}" if match else None


def extract_sqft(text: str) -> Optional[int]:
    match = AREA_PATTERN.search(text)
    return int(match.group(1).replace(',', '')) if match else None


def extract_localities(text: str) -> list[str]:
    text = text.lower()
    return [locality for locality in LOCALITIES if locality in text]


def extract_phones(text: str) -> list[str]:
    """Unique Indian phone numbers with spaces/dashes removed."""
    phones = {re.sub(r'[\s-]', '', match.group())
              for pattern in PHONE_PATTERNS for match in pattern.finditer(text)}
    return sorted(phone for phone in phones if len(phone) >= 10)


def parse_rental_post(post: dict) -> Optional[dict]:
    """Parse a facebook-scraper post; None unless it looks like a rental post."""
    text = post.get('text') or ''
    if len(text) < 20:
        return None
    rent, bhk = extract_rent(text), extract_bhk(text)
    if not rent and not bhk:
        return None

    return {
        'source': 'facebook',
        'post_id': post.get('post_id', ''),
        'text': text[:1000],
        'rent': rent,
        'bhk': bhk,
        'sqft': extract_sqft(text),
        'localities': extract_localities(text),
        'phones': extract_phones(text),
        'images': (post.get('images') or [])[:10],
        'time': str(post.get('time', '')),
        'username': post.get('username', ''),
        'url': post.get('post_url', ''),
        'likes': post.get('likes', 0),
        'comments': post.get('comments', 0),
    }


def scrape_group(
    group_id: str,
    pages: int = 20,
    cookies: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> list[dict]:
    """Scrape rental posts from a Facebook group (cookies = Netscape cookie file path)."""
    from facebook_scraper import get_posts, set_cookies

    if cookies:
        set_cookies(cookies)

    print(f"  Scraping group {group_id}, {pages} pages...")
    all_posts, rental_posts = [], []
    try:
        for post_count, post in enumerate(get_posts(group=group_id, pages=pages, options={"progress": True}), 1):
            all_posts.append(post)
            parsed = parse_rental_post(post)
            if parsed:
                rental_posts.append(parsed)
            if post_count % 50 == 0:
                print(f"    Processed {post_count} posts, found {len(rental_posts)} rental posts")
            time.sleep(0.5)  # be polite
    except Exception as e:  # facebook-scraper raises many ad-hoc errors (login walls, rate limits)
        print(f"  [!] Error: {e}")

    print(f"  Done. {len(all_posts)} total posts, {len(rental_posts)} rental posts")

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"fb_raw_{group_id}.json").write_text(json.dumps(all_posts, indent=2, default=str))
        parsed_path = output_dir / f"fb_rentals_{group_id}.json"
        parsed_path.write_text(json.dumps(rental_posts, indent=2))
        print(f"  Saved to {parsed_path}")

    return rental_posts


def scrape_all(cookies: Optional[str] = None, pages: int = 20) -> list[dict]:
    """Scrape all configured groups and print the best in-budget posts with phone numbers."""
    all_rentals = []
    for name, group_id in GROUPS.items():
        print(f"\nScraping {name}...")
        all_rentals.extend(scrape_group(group_id, pages=pages, cookies=cookies, output_dir=FACEBOOK_POSTS_DIR))
    print(f"\nTotal rental posts found: {len(all_rentals)}")

    low, high = RENT_BUDGET
    in_budget = [post for post in all_rentals if post['rent'] and low <= post['rent'] <= high]
    with_phone = [post for post in in_budget if post['phones']]
    print(f"In budget ({low // 1000}K-{high // 1000}K): {len(in_budget)}")
    print(f"With phone numbers: {len(with_phone)}")

    if in_budget:
        print("\n=== TOP FB LISTINGS (in budget, with phone) ===\n")
        for rank, post in enumerate(sorted(with_phone, key=lambda p: -p['rent'])[:20], 1):
            areas = ', '.join(post['localities'][:3]) or 'unknown area'
            print(f"{rank}. Rs.{post['rent']:,}/mo | {post['bhk'] or '?'} | {post['sqft'] or '?'}sqft | {areas}")
            print(f"   Phone: {', '.join(post['phones'])}")
            print(f"   {post['text'][:150]}...")
            print(f"   {post['url']}\n")

    return all_rentals


if __name__ == '__main__':
    if len(sys.argv) > 1:
        scrape_all(cookies=sys.argv[1])
    else:
        print(__doc__)
