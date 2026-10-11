from __future__ import annotations

from typing import Any


def watchlist_reducer(current: list[dict[str, Any]] | None, updates: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Merge watchlist changes by TMDB id (or title) instead of duplicating titles."""
    merged = list(current or [])
    positions = {
        str(item.get('tmdb_id') or item.get('title', '')).lower(): index
        for index, item in enumerate(merged)
    }
    for item in updates or []:
        key = str(item.get('tmdb_id') or item.get('title', '')).lower()
        if item.get('_remove'):
            merged = [existing for existing in merged if str(existing.get('title', '')).lower() != key]
            positions = {
                str(existing.get('tmdb_id') or existing.get('title', '')).lower(): index
                for index, existing in enumerate(merged)
            }
            continue
        if key in positions:
            merged[positions[key]] = {**merged[positions[key]], **item}
        else:
            positions[key] = len(merged)
            merged.append(item)
    return merged
