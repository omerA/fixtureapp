"""
build_team_index.py — Scrape every NCSA division once and build a team index.

Run this once at the start of the season, or weekly during the season to catch
late-added teams. It produces team_index.json:

    {
      "scraped_at": "2026-05-11T...",
      "by_team": {
        "Tenafly-B12B-Schwartzberg": {
          "club": "Tenafly",
          "coach": "Schwartzberg",
          "division": "B12B"
        },
        ...
      },
      "by_club": {
        "Tenafly": ["Tenafly-B12B-Schwartzberg", ...],
        ...
      },
      "divisions": ["B08A4", "B08A7", ...]
    }

Run:
    python build_team_index.py
    python build_team_index.py --divisions B12B,B10A   # just these
    python build_team_index.py --no-cache              # force fresh fetch
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Pulled from the form HTML you provided. Hard-coded because (a) it's stable
# and (b) it lets us know the moment a new division appears.
ALL_DIVISIONS = [
    # Boys
    "B08A4","B08A7","B08B4","B08B7","B08C4","B08C7","B08D4","B08D7","B08E4","B08F4",
    "B09A","B09B","B09C","B09D","B09E","B09EW","B09F","B09G","B09GW","B09H","B09R","B09XB","B09XW",
    "B10A","B10AB","B10BB","B10C","B10D","B10DB","B10E","B10F","B10FB","B10G","B10GB","B10H","B10HB","B10R","B10XB","B10XW",
    "B11A","B11B","B11C","B11D","B11DB","B11E","B11EB","B11F","B11G","B11GB","B11H","B11HB","B11R","B11XB","B11XW",
    "B12A","B12B","B12C","B12D","B12EB","B12EW","B12F","B12G","B12GB","B12GW","B12H","B12R","B12XB","B12XW",
    "B13A","B13B","B13C","B13D","B13E","B13FB","B13FW","B13G","B13R","B13XW",
    "B14A","B14B","B14C","B14D","B14E","B14F","B14R","B14XB","B14XW",
    "B15A","B15B","B15C","B15D","B15E","B15F","B15R",
    "B16A","B16R","B17A","B17R","B18R","B19A","B19B","B19C","B19D","B19R",
    # Girls
    "G08A4","G08A7","G08B4","G08B7","G08C4",
    "G09A","G09B","G09C","G09D","G09E","G09F","G09R","G09XB",
    "G10A","G10B","G10C","G10D","G10E","G10F","G10G","G10H","G10R","G10XB","G10XW",
    "G11A","G11B","G11C","G11D","G11E","G11F","G11R","G11XB","G11XW",
    "G12A","G12B","G12C","G12D","G12E","G12F","G12R","G12XB","G12XW",
    "G13A","G13B","G13C","G13D","G13E","G13F","G13R","G13XB",
    "G14A","G14B","G14CB","G14CW","G14R",
    "G15A","G15B","G15C","G15R","G16R","G17R","G19A","G19B","G19C","G19R",
]


def parse_team_name(raw: str) -> tuple[str, str]:
    """Parse 'Club-Flight-Coach' into (club, coach). Tolerant of extra spaces."""
    parts = [p.strip() for p in raw.strip().split("-")]
    if len(parts) >= 3:
        return parts[0], parts[-1]
    return raw, ""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--divisions", help="Comma-separated subset (default: all)")
    ap.add_argument("--cache-dir", default="./cache", help="Where to cache HTML")
    ap.add_argument("--no-cache", action="store_true", help="Force fresh fetch")
    ap.add_argument("--out", default="./team_index.json", help="Output path")
    ap.add_argument("--delay", type=float, default=2.0, help="Seconds between requests")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    from fetcher import StandingsFetcher
    from team_extractor import extract_team_names

    divisions = args.divisions.split(",") if args.divisions else ALL_DIVISIONS
    fetcher = StandingsFetcher(
        cache_dir=Path(args.cache_dir),
        min_delay_seconds=args.delay,
    )

    by_team: dict[str, dict] = {}
    by_club: dict[str, list[str]] = defaultdict(list)
    empty_divisions: list[str] = []
    errors: list[tuple[str, str]] = []

    total = len(divisions)
    for i, division in enumerate(divisions, 1):
        print(f"[{i}/{total}] {division}...", end=" ", flush=True)
        try:
            result = fetcher.fetch(division, force_refresh=args.no_cache)
            team_names = extract_team_names(result.html)
            if not team_names:
                empty_divisions.append(division)
                print("empty (no flight yet)")
                continue
            for name in team_names:
                club, coach = parse_team_name(name)
                by_team[name] = {"club": club, "coach": coach, "division": division}
                by_club[club].append(name)
            cached_marker = " [cached]" if result.from_cache else ""
            print(f"{len(team_names)} teams{cached_marker}")
        except Exception as e:
            errors.append((division, str(e)))
            print(f"ERROR: {e}")

    # Deduplicate by_club lists (a team only appears in one division, but defensive)
    by_club_dedup = {club: sorted(set(teams)) for club, teams in by_club.items()}

    output = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": "https://www.ncsanj.com/standings.cfm",
        "divisions": divisions,
        "empty_divisions": empty_divisions,
        "errors": dict(errors) if errors else {},
        "by_team": by_team,
        "by_club": by_club_dedup,
    }

    out_path = Path(args.out)
    out_path.write_text(json.dumps(output, indent=2, sort_keys=True))

    print()
    print("=" * 60)
    print(f"Wrote {out_path}")
    print(f"  Total divisions queried: {total}")
    print(f"  Divisions with teams:    {total - len(empty_divisions) - len(errors)}")
    print(f"  Empty divisions:         {len(empty_divisions)}")
    print(f"  Errors:                  {len(errors)}")
    print(f"  Total teams indexed:     {len(by_team)}")
    print(f"  Total clubs:             {len(by_club_dedup)}")

    # Tenafly-specific summary
    tenafly_teams = by_club_dedup.get("Tenafly", [])
    if tenafly_teams:
        print(f"\nTenafly teams ({len(tenafly_teams)}):")
        for t in tenafly_teams:
            info = by_team[t]
            print(f"  {info['division']:>6}  {t}")
    else:
        print("\nNo Tenafly teams found. Possible club name variants in by_club:")
        for club in sorted(by_club_dedup.keys()):
            if "tena" in club.lower() or "tenafly" in club.lower():
                print(f"  {club}: {by_club_dedup[club]}")

    if errors:
        print("\nErrors:")
        for div, err in errors:
            print(f"  {div}: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
