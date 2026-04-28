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
    """Merge multiple star/dismissal dicts. Star wins over dismiss. Later source wins timestamp."""
    merged = {"starred": {}, "dismissed": {}}
    for src in sources:
        if not isinstance(src, dict):
            continue
        for k, v in src.get("starred", {}).items():
            merged["starred"][k] = v
        for k, v in src.get("dismissed", {}).items():
            merged["dismissed"][k] = v
    # Star wins over dismiss
    for k in merged["starred"]:
        merged["dismissed"].pop(k, None)
    return merged
