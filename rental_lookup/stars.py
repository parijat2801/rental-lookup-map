"""Merge stars/dismissals from several copies (published stars.json, repo cache, browser).

Each copy looks like {"starred": {url: ts}, "dismissed": {url: ts}} where `ts` is
an epoch-ms timestamp. A negative timestamp is a tombstone: the user un-starred /
un-dismissed at time abs(ts). Corrupted input never destroys valid data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

STAR_LISTS = ("starred", "dismissed")


def parse_json_object(text: str) -> dict:
    """Parse JSON text, returning {} for any invalid/unexpected input."""
    if not text or not text.strip():
        return {}
    try:
        data = json.loads(text)
    except ValueError:  # includes json.JSONDecodeError
        return {}
    return data if isinstance(data, dict) else {}


def merge_stars(copies: list, keep_tombstones: bool = False) -> dict:
    """Merge star/dismissal dicts; for each URL the most recent action wins.

    "Most recent" compares abs(ts), so a tombstone (-300) beats an older star (200).
    A URL that ends up both starred and dismissed stays starred only.
    Tombstones are dropped from the output unless `keep_tombstones` is set
    (useful when the result will be merged again later).
    """
    merged: dict = {name: {} for name in STAR_LISTS}
    for copy in copies:
        if not isinstance(copy, dict):
            continue
        for name in STAR_LISTS:
            entries = copy.get(name)
            if not isinstance(entries, dict):
                continue
            latest = merged[name]
            for url, ts in entries.items():
                if isinstance(ts, bool) or not isinstance(ts, (int, float)):
                    continue
                if url not in latest or abs(ts) > abs(latest[url]):
                    latest[url] = ts

    if not keep_tombstones:
        for name in STAR_LISTS:
            merged[name] = {url: ts for url, ts in merged[name].items() if ts > 0}
    for url, ts in merged["starred"].items():
        if ts > 0 and merged["dismissed"].get(url, 0) > 0:
            del merged["dismissed"][url]
    return merged


def main(argv: list) -> None:
    """CLI used by CI: python -m rental_lookup.stars OUTPUT INPUT [INPUT ...]

    Missing or corrupt inputs count as empty. Refuses to write an empty result,
    since that almost certainly means every input failed to load.
    """
    if len(argv) < 2:
        raise SystemExit(main.__doc__)
    output_path, input_paths = Path(argv[0]), [Path(p) for p in argv[1:]]
    copies = [parse_json_object(p.read_text()) if p.exists() else {} for p in input_paths]
    merged = merge_stars(copies)
    if not merged["starred"] and not merged["dismissed"]:
        raise SystemExit("Refusing to publish empty stars — all sources were unreadable")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(merged, indent=2))
    print(f"Merged: {len(merged['starred'])} starred, {len(merged['dismissed'])} dismissed")


if __name__ == "__main__":
    main(sys.argv[1:])
