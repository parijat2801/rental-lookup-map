"""Rank NoBroker listings into output/results.csv.

Run: rental-map-rank [--cookie COOKIE]
 or: python -m rental_lookup [--cookie COOKIE]

Uses the pages saved by `rental-map-fetch nobroker`, fetching any missing neighbourhoods.
"""
import argparse

from rental_lookup.ranking_report import main as write_ranking


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="rental-map-rank", description=__doc__.splitlines()[0])
    parser.add_argument("--cookie", default="",
                        help="Cookie header for NoBroker, only needed if requests get blocked")
    write_ranking(cookie=parser.parse_args(argv).cookie)


if __name__ == "__main__":
    main()
