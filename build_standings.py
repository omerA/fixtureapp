"""
build_standings.py — Parse full standings for every division in the watch-list.

Reads team_index.json to find which divisions contain Tenafly teams (or any
club you specify), then fetches + parses each one into a rich JSON file under
./standings/<DIVISION>.json.

Because the index build already cached all HTML, the first run is free
(no new requests). Subsequent runs respect the 12-hour cache too.

Run:
    python build_standings.py                         # all Tenafly divisions
    python build_standings.py --club Tenafly          # same, explicit
    python build_standings.py --divisions B12A,G12A   # specific overrides
    python build_standings.py --all                   # every division in index
    python build_standings.py -v                      # verbose (show each team)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


def load_index(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"team_index.json not found at {path}. Run build_team_index.py first.")
    return json.loads(path.read_text())


def divisions_for_club(index: dict, club: str) -> list[str]:
    teams = index.get("by_club", {}).get(club, [])
    return sorted({index["by_team"][t]["division"] for t in teams})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--club", default="Tenafly", help="Club to watch (default: Tenafly)")
    ap.add_argument("--divisions", help="Comma-separated division list (overrides --club)")
    ap.add_argument("--all", dest="all_divs", action="store_true",
                    help="Fetch every non-empty division in the index")
    ap.add_argument("--index", default="./team_index.json", help="Path to team_index.json")
    ap.add_argument("--cache-dir", default="./cache", help="HTML cache directory")
    ap.add_argument("--out-dir", default="./standings", help="Output directory for JSON files")
    ap.add_argument("--no-cache", action="store_true", help="Force fresh fetch")
    ap.add_argument("--delay", type=float, default=2.0, help="Seconds between requests")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    from fetcher import StandingsFetcher, STANDINGS_URL
    from parser import parse_standings

    index = load_index(Path(args.index))

    if args.divisions:
        divisions = [d.strip() for d in args.divisions.split(",")]
    elif args.all_divs:
        divisions = [d for d in index.get("divisions", [])
                     if d not in index.get("empty_divisions", [])]
    else:
        divisions = divisions_for_club(index, args.club)
        if not divisions:
            sys.exit(
                f"No divisions found for club '{args.club}' in {args.index}.\n"
                f"Available clubs: {sorted(index.get('by_club', {}).keys())}"
            )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fetcher = StandingsFetcher(
        cache_dir=Path(args.cache_dir),
        min_delay_seconds=args.delay,
    )

    errors: list[tuple[str, str]] = []
    written: list[str] = []
    total = len(divisions)

    for i, division in enumerate(divisions, 1):
        print(f"[{i}/{total}] {division}...", end=" ", flush=True)
        try:
            result = fetcher.fetch(division, force_refresh=args.no_cache)
            cached_marker = " [cached]" if result.from_cache else ""

            standings = parse_standings(result.html, division, source_url=STANDINGS_URL)

            out_path = out_dir / f"{division}.json"
            out_path.write_text(json.dumps(standings.to_dict(), indent=2, sort_keys=True))
            written.append(division)

            club_teams = [t for t in standings.teams if t.club == args.club]
            if club_teams:
                t = club_teams[0]
                summary = (
                    f"{t.wins}W {t.losses}L {t.draws}D  "
                    f"pts:{t.points}  gd:{t.goal_diff:+d}  form:{t.form}"
                )
                print(f"{t.team_raw}{cached_marker}  ->  {summary}")
            else:
                print(f"{len(standings.teams)} teams{cached_marker} (no {args.club})")

            if args.verbose:
                for t in standings.teams:
                    print(
                        f"    {t.team_raw:<35}  "
                        f"{t.wins}W {t.losses}L {t.draws}D  "
                        f"pts:{t.points:>3}  gd:{t.goal_diff:+d}"
                    )

        except Exception as e:
            errors.append((division, str(e)))
            print(f"ERROR: {e}")
            log.exception("failed on %s", division)

    print()
    print("=" * 60)
    print(f"Wrote {len(written)} files to {out_dir}/")
    print(f"  Errors: {len(errors)}")

    if errors:
        print("\nErrors:")
        for div, err in errors:
            print(f"  {div}: {err}")
        sys.exit(1)

    # Summary: show all watched-club teams sorted by division
    club_summary: list[tuple[str, object]] = []
    for division in written:
        data = json.loads((out_dir / f"{division}.json").read_text())
        for t in data["teams"]:
            if t["club"] == args.club:
                club_summary.append((division, t))

    if club_summary:
        print(f"\n{args.club} teams ({len(club_summary)}):")
        print(f"  {'Division':<8} {'Team':<38} {'W':>2} {'L':>2} {'D':>2} {'Pts':>4} {'GD':>4}  Form")
        print("  " + "-" * 72)
        for division, t in sorted(club_summary):
            print(
                f"  {division:<8} {t['team_raw']:<38} "
                f"{t['wins']:>2} {t['losses']:>2} {t['draws']:>2} "
                f"{t['points']:>4} {t['goal_diff']:>+4}  {t['form']}"
            )


if __name__ == "__main__":
    main()
