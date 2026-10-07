"""
build_team_index.py — Scrape every NCSA division once and build a team index.

Run this once at the start of the season, or weekly during the season to catch
late-added teams. The division list is read from the live standings form on
every run (see divisions.py), so a new season's flights are picked up without
a code change. It produces team_index.json:

    {
      "scraped_at": "2026-05-11T...",
      "season": "2026-spring",
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
    python build_team_index.py                         # discover divisions
    python build_team_index.py --divisions B12B,B10A   # just these, no discovery
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


def parse_team_name(raw: str) -> tuple[str, str]:
    """Parse 'Club-Flight-Coach' into (club, coach). Tolerant of extra spaces."""
    parts = [p.strip() for p in raw.strip().split("-")]
    if len(parts) >= 3:
        return parts[0], parts[-1]
    return raw, ""


def load_previous_divisions(path: Path) -> list[str] | None:
    """Return the `divisions` list of an existing index file, or None."""
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
        divisions = previous.get("divisions")
    except (OSError, ValueError, AttributeError):
        return None
    return divisions if isinstance(divisions, list) else None


def load_previous_team_count(path: Path) -> int:
    """Number of teams in the existing index file, or 0 if there is none."""
    try:
        return len(json.loads(path.read_text(encoding="utf-8")).get("by_team", {}))
    except (OSError, ValueError):
        return 0


def report_division_changes(previous: list[str] | None, current: list[str]) -> None:
    """Print which division codes appeared or vanished since the last index."""
    from divisions import diff_divisions

    if previous is None:
        print("  No previous index to compare against.")
        return
    added, removed = diff_divisions(previous, current)
    print(f"  Added since last index ({len(added)}): {', '.join(added) or 'none'}")
    print(f"  Removed since last index ({len(removed)}): {', '.join(removed) or 'none'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--divisions", help="Comma-separated codes to scrape, skipping discovery "
                         "(default: every division on the live standings form)")
    ap.add_argument("--cache-dir", default="./cache", help="Where to cache HTML")
    ap.add_argument("--no-cache", action="store_true", help="Force fresh fetch")
    ap.add_argument("--out", default="./team_index.json", help="Output path")
    ap.add_argument("--delay", type=float, default=2.0, help="Seconds between requests")
    ap.add_argument("--force", action="store_true",
                    help="Write the index even if it has far fewer teams than the previous one")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    from divisions import DivisionDiscoveryError, discover_divisions, season_for
    from fetcher import StandingsFetcher
    from team_extractor import extract_team_names

    fetcher = StandingsFetcher(
        cache_dir=Path(args.cache_dir),
        min_delay_seconds=args.delay,
    )
    out_path = Path(args.out)

    if args.divisions:
        # Explicit override: scrape exactly these, no discovery request.
        divisions = args.divisions.split(",")
    else:
        # No fallback list on purpose: last season's codes are the failure
        # mode, so if discovery fails we stop before touching the index.
        try:
            divisions = discover_divisions(fetcher)
        except (DivisionDiscoveryError, RuntimeError, OSError) as e:
            sys.exit(f"Division discovery failed, index not updated: {e}")
        print(f"Discovered {len(divisions)} divisions on the standings form.")
        report_division_changes(load_previous_divisions(out_path), divisions)
        print()

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

    # The app treats a followed team that is missing from the index as gone for
    # the season, so a partial index must never replace a good one.
    if errors:
        print("\nErrors, index not updated:")
        for div, err in errors:
            print(f"  {div}: {err}")
        sys.exit(1)
    if not by_team:
        sys.exit("No teams found in any division, index not updated.")
    previous_count = load_previous_team_count(out_path)
    if not args.divisions and not args.force and previous_count and len(by_team) < previous_count / 2:
        sys.exit(
            f"Only {len(by_team)} teams found, previous index had {previous_count}; "
            "index not updated. Re-run with --force if this is expected."
        )

    # Deduplicate by_club lists (a team only appears in one division, but defensive)
    by_club_dedup = {club: sorted(set(teams)) for club, teams in by_club.items()}

    scraped_at = datetime.now(timezone.utc)
    output = {
        "scraped_at": scraped_at.isoformat(),
        "season": season_for(scraped_at.date()),
        "source": "https://www.ncsanj.com/standings.cfm",
        "divisions": divisions,
        "empty_divisions": empty_divisions,
        "errors": dict(errors) if errors else {},
        "by_team": by_team,
        "by_club": by_club_dedup,
    }

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


if __name__ == "__main__":
    main()
