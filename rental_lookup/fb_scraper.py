"""
Facebook Flat & Flatmates group scraper.

Usage:
    # First, get your FB cookies from Chrome DevTools:
    # 1. Go to facebook.com, open DevTools > Application > Cookies
    # 2. Copy the value of 'c_user' and 'xs' cookies
    # Or export all cookies as a Netscape cookie file

    python3 -m rental_lookup.fb_scraper
"""

import json
import re
import time
from pathlib import Path
from typing import List, Optional

# Bangalore Flat & Flatmates groups (add more as needed)
GROUPS = {
    "flat-and-flatmates-bangalore": "344060792364300",
    # Add other group IDs here
}

# Rent extraction patterns
RENT_PATTERNS = [
    r'(?:rent|rental|price|cost|amount)\s*[:\-]?\s*(?:rs\.?|inr|₹)\s*([\d,]+)',
    r'(?:rs\.?|inr|₹)\s*([\d,]+)\s*(?:/\s*(?:month|mon|pm|per month))',
    r'(?:rs\.?|inr|₹)\s*([\d,]+)',
    r'([\d,]+)\s*(?:rs|inr|₹)',
    r'([\d]+k)\s*(?:rent|pm|per month)',
]

# BHK patterns
BHK_PATTERN = re.compile(r'(\d)\s*bhk', re.IGNORECASE)

# Area patterns
AREA_PATTERNS = [
    r'(\d[\d,]*)\s*(?:sq\.?\s*ft|sqft|sft|square\s*feet)',
]

# Bangalore locality keywords
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

# Phone number patterns (Indian)
PHONE_PATTERNS = [
    r'(?:\+91[\s-]?)?[6-9]\d{9}',
    r'(?:\+91[\s-]?)?\d{5}[\s-]?\d{5}',
]


def extract_rent(text: str) -> Optional[int]:
    """Extract rent amount from post text."""
    text_lower = text.lower()
    for pattern in RENT_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            val = match.group(1).replace(',', '')
            if val.endswith('k'):
                return int(float(val[:-1]) * 1000)
            try:
                amount = int(val)
                # Sanity check: rent should be between 5K and 2L
                if 5000 <= amount <= 200000:
                    return amount
            except ValueError:
                continue
    return None


def extract_bhk(text: str) -> Optional[str]:
    """Extract BHK from post text."""
    match = BHK_PATTERN.search(text)
    if match:
        return f"BHK{match.group(1)}"
    return None


def extract_sqft(text: str) -> Optional[int]:
    """Extract square footage from post text."""
    for pattern in AREA_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1).replace(',', ''))
            except ValueError:
                continue
    return None


def extract_localities(text: str) -> List[str]:
    """Extract Bangalore locality names from post text."""
    text_lower = text.lower()
    found = []
    for loc in LOCALITIES:
        if loc in text_lower:
            found.append(loc)
    return found


def extract_phones(text: str) -> List[str]:
    """Extract phone numbers from post text."""
    phones = []
    for pattern in PHONE_PATTERNS:
        for match in re.finditer(pattern, text):
            phone = re.sub(r'[\s-]', '', match.group())
            if len(phone) >= 10:
                phones.append(phone)
    return list(set(phones))


def parse_fb_post(post: dict) -> Optional[dict]:
    """Parse a facebook-scraper post dict into our format."""
    text = post.get('text', '') or ''
    if not text or len(text) < 20:
        return None

    rent = extract_rent(text)
    bhk = extract_bhk(text)
    localities = extract_localities(text)
    phones = extract_phones(text)
    sqft = extract_sqft(text)

    # Must have at least rent or BHK to be a rental post
    if not rent and not bhk:
        return None

    images = post.get('images', []) or []

    return {
        'source': 'facebook',
        'post_id': post.get('post_id', ''),
        'text': text[:1000],
        'rent': rent,
        'bhk': bhk,
        'sqft': sqft,
        'localities': localities,
        'phones': phones,
        'images': images[:10],
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
) -> List[dict]:
    """Scrape rental posts from a Facebook group."""
    from facebook_scraper import get_posts, set_cookies

    if cookies:
        # cookies can be a file path to Netscape cookie file
        set_cookies(cookies)

    print(f"  Scraping group {group_id}, {pages} pages...")
    all_posts = []
    rental_posts = []

    try:
        for i, post in enumerate(get_posts(group=group_id, pages=pages, options={"progress": True})):
            all_posts.append(post)
            parsed = parse_fb_post(post)
            if parsed:
                rental_posts.append(parsed)

            if (i + 1) % 50 == 0:
                print(f"    Processed {i+1} posts, found {len(rental_posts)} rental posts")

            time.sleep(0.5)  # be polite

    except Exception as e:
        print(f"  [!] Error: {e}")

    print(f"  Done. {len(all_posts)} total posts, {len(rental_posts)} rental posts")

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        # Save raw posts
        raw_path = output_dir / f"fb_raw_{group_id}.json"
        with open(raw_path, 'w') as f:
            json.dump([{k: str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v
                       for k, v in p.items()} for p in all_posts], f, indent=2, default=str)
        # Save parsed rental posts
        parsed_path = output_dir / f"fb_rentals_{group_id}.json"
        with open(parsed_path, 'w') as f:
            json.dump(rental_posts, f, indent=2)
        print(f"  Saved to {parsed_path}")

    return rental_posts


def scrape_all(cookies: Optional[str] = None, pages: int = 20) -> List[dict]:
    """Scrape all configured groups."""
    output_dir = Path("data/fb")
    all_rentals = []

    for name, group_id in GROUPS.items():
        print(f"\nScraping {name}...")
        rentals = scrape_group(group_id, pages=pages, cookies=cookies, output_dir=output_dir)
        all_rentals.extend(rentals)

    print(f"\nTotal rental posts found: {len(all_rentals)}")

    # Filter to our budget range
    in_budget = [r for r in all_rentals if r['rent'] and 25000 <= r['rent'] <= 70000]
    print(f"In budget (25K-70K): {len(in_budget)}")

    # Posts with phone numbers
    with_phone = [r for r in in_budget if r['phones']]
    print(f"With phone numbers: {len(with_phone)}")

    # Summary
    if in_budget:
        print("\n=== TOP FB LISTINGS (in budget, with phone) ===\n")
        for i, r in enumerate(sorted(with_phone, key=lambda x: -(x['rent'] or 0))[:20], 1):
            locs = ', '.join(r['localities'][:3]) if r['localities'] else 'unknown area'
            print(f"{i}. Rs.{r['rent']:,}/mo | {r['bhk'] or '?'} | {r['sqft'] or '?'}sqft | {locs}")
            print(f"   Phone: {', '.join(r['phones'])}")
            print(f"   {r['text'][:150]}...")
            print(f"   {r['url']}")
            print()

    return all_rentals


if __name__ == '__main__':
    import sys
    cookies = sys.argv[1] if len(sys.argv) > 1 else None
    if not cookies:
        print("Usage: python3 -m rental_lookup.fb_scraper <path_to_cookies.txt>")
        print()
        print("To get cookies:")
        print("1. Install 'Get cookies.txt LOCALLY' Chrome extension")
        print("2. Go to facebook.com (logged in)")
        print("3. Click extension > Export as Netscape cookie file")
        print("4. Save as cookies.txt")
        print()
        print("Then run: python3 -m rental_lookup.fb_scraper cookies.txt")
    else:
        scrape_all(cookies=cookies)
