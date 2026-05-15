"""
build_schedules.py — Fetch + parse game schedules for watched divisions.

Outputs one JSON file per division to ./schedules/<DIVISION>.json.

Run:
    python build_schedules.py                        # all Tenafly divisions
    python build_schedules.py --club Tenafly         # same, explicit
    python build_schedules.py --divisions B12A,G12A  # specific overrides
    python build_schedules.py --all                  # every division in index
    python build_schedules.py --no-cache             # force fresh fetch
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
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
    ap.add_argument("--out-dir", default="./schedules", help="Output directory for JSON files")
    ap.add_argument("--no-cache", action="store_true", help="Force fresh fetch")
    ap.add_argument("--delay", type=float, default=2.0, help="Seconds between requests")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    from fetcher import StandingsFetcher, SCHEDULE_URL
    from schedule_parser import parse_schedule

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
            result = fetcher.fetch_schedule(division, force_refresh=args.no_cache)
            cached_marker = " [cached]" if result.from_cache else ""

            schedule = parse_schedule(result.html, division, source_url=SCHEDULE_URL)

            out_path = out_dir / f"{division}.json"
            out_path.write_text(json.dumps(schedule.to_dict(), indent=2, sort_keys=True))
            written.append(division)

            upcoming = [g for g in schedule.games if g.is_upcoming]
            played = [g for g in schedule.games if not g.is_upcoming]
            print(
                f"{len(schedule.games)} games{cached_marker}  "
                f"({len(played)} played, {len(upcoming)} upcoming)"
            )

            if args.verbose:
                for g in sorted(schedule.games, key=lambda x: (x.date, x.time)):
                    status = "upcoming" if g.is_upcoming else f"{g.home_score}-{g.away_score}"
                    print(
                        f"    {g.date} {g.time:<10}  "
                        f"{g.home_team:<35} vs {g.away_team:<35}  [{status}]"
                    )

        except Exception as e:
            errors.append((division, str(e)))
            print(f"ERROR: {e}")
            log.exception("failed on %s", division)

    print()
    print("=" * 60)
    print(f"Wrote {len(written)} files to {out_dir}/")
    if errors:
        print(f"  Errors: {len(errors)}")
        for div, err in errors:
            print(f"  {div}: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
