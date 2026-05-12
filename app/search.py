from __future__ import annotations

import re
from typing import Any


def division_label(code: str) -> str:
    """'B12A' -> 'Boys U12 · Flight A',  'G09R' -> 'Girls U9 · Recreational'"""
    m = re.match(r"^([BG])(\d{2})([A-Za-z0-9]+)$", code)
    if not m:
        return code
    gender = "Boys" if m.group(1) == "B" else "Girls"
    age = str(int(m.group(2)))  # strip leading zero: "08" -> "8"
    flight = m.group(3)
    suffix = "Recreational" if flight == "R" else f"Flight {flight}"
    return f"{gender} U{age} · {suffix}"


def search_teams(
    query: str, index: dict, limit: int = 15
) -> list[dict[str, Any]]:
    """
    Case-insensitive substring search across team_key, club, coach, and division.
    Requires at least 2 characters to avoid returning the whole index.
    """
    q = query.lower().strip()
    if len(q) < 2:
        return []
    results: list[dict[str, Any]] = []
    for team_key, info in index.get("by_team", {}).items():
        haystack = (
            f"{team_key} {info['club']} {info['coach']} {info['division']}"
        ).lower()
        if q in haystack:
            results.append(
                {
                    "team_key": team_key,
                    "club": info["club"],
                    "coach": info["coach"],
                    "division": info["division"],
                    "division_label": division_label(info["division"]),
                }
            )
            if len(results) >= limit:
                break
    return results
