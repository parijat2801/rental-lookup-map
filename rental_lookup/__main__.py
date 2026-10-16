"""`python -m rental_lookup [COOKIE]` — fetch, score and rank NoBroker listings."""
import sys

from rental_lookup.ranking_report import main

if __name__ == "__main__":
    main(cookie=sys.argv[1] if len(sys.argv) > 1 else "")
