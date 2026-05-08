"""Merge stars/dismissals from multiple sources (jsonblob, Gist, repo).

Used by CI to combine stars from all sources into one canonical file.
Handles corrupted JSON gracefully — never loses valid data.
"""
import json


def load_json_safe(text: str) -> dict:
    """Parse JSON text, returning {} for any invalid/unexpected input."""
    if not text or not text.strip():
        return {}
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def merge_stars(sources: list) -> dict:
    """Merge multiple star/dismissal dicts.

    Negative values are tombstones (intentional deletions).
    A tombstone (-300) beats a positive value (200) if abs(tombstone) > positive.
    Positive star wins over positive dismiss for the same URL.
    Output never contains negative values.
    """
    merged = {"starred": {}, "dismissed": {}}
    for src in sources:
        if not isinstance(src, dict):
            continue
        for k, v in src.get("starred", {}).items():
            if not isinstance(v, (int, float)):
                continue
            existing = merged["starred"].get(k)
            if existing is None or abs(v) > abs(existing):
                merged["starred"][k] = v
        for k, v in src.get("dismissed", {}).items():
            if not isinstance(v, (int, float)):
                continue
            existing = merged["dismissed"].get(k)
            if existing is None or abs(v) > abs(existing):
                merged["dismissed"][k] = v
    # Strip tombstones (negative values)
    merged["starred"] = {k: v for k, v in merged["starred"].items() if v > 0}
    merged["dismissed"] = {k: v for k, v in merged["dismissed"].items() if v > 0}
    # Positive star wins over positive dismiss
    for k in merged["starred"]:
        merged["dismissed"].pop(k, None)
    return merged
