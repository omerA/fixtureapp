"""
merge_standings.py — Merge freshly-scraped standings with the last committed version.

After build_standings.py writes fresh JSON to ./standings/, this script:
  1. Reads the previous version of each file from git HEAD
  2. Merges game history (union of old + new; fresh data wins on conflict)
  3. Keeps standings stats (W/L/D/Pts) from the fresh scrape (site is authoritative)
  4. Writes the merged file back to ./standings/
  5. Prints a summary of changes to stdout

Exit code 0 always; callers should check git status to decide whether to commit.

Run:
    python merge_standings.py
    python merge_standings.py --standings-dir ./standings
    python merge_standings.py --verbose
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _git_show(path: Path) -> dict | None:
    """Return parsed JSON from the HEAD version of a tracked file, or None."""
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{path}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError:
        # File doesn't exist in HEAD (new division this run)
        return None
    except json.JSONDecodeError:
        log.warning("Could not parse HEAD version of %s", path)
        return None


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

def _index_games(teams: list[dict]) -> dict[str, dict[str, dict]]:
    """Build {team_raw: {game_number: game_dict}} from a list of team dicts."""
    index: dict[str, dict[str, dict]] = {}
    for team in teams:
        index[team["team_raw"]] = {
            g["game_number"]: g for g in team.get("games", [])
        }
    return index


def merge_division(old: dict, new: dict) -> tuple[dict, list[str]]:
    """
    Merge old (HEAD) and new (freshly scraped) division data.

    Strategy:
    - Standings stats (W/L/D/Pts/GF/GA) → always from `new` (site is truth)
    - Games → union of old + new; new wins on conflicting game_number
    - Games in old but missing from new → preserved (conservative; NCSA may lag)

    Returns (merged_division_dict, list_of_change_descriptions).
    """
    changes: list[str] = []
    old_game_index = _index_games(old.get("teams", []))
    new_teams_by_key = {t["team_raw"]: t for t in new.get("teams", [])}
    old_teams_by_key = {t["team_raw"]: t for t in old.get("teams", [])}

    merged_teams: list[dict] = []

    for team_raw, new_team in new_teams_by_key.items():
        old_team = old_teams_by_key.get(team_raw)

        new_games = {g["game_number"]: g for g in new_team.get("games", [])}
        old_games = old_game_index.get(team_raw, {})

        # Detect new games and score changes
        for gnum, new_game in new_games.items():
            if gnum not in old_games:
                changes.append(
                    f"  {team_raw}: new game #{gnum} "
                    f"({new_game.get('date', '?')}, "
                    f"{new_game.get('goals_for')}-{new_game.get('goals_against')} "
                    f"vs {new_game.get('opponent_club', '?')})"
                )
            else:
                og = old_games[gnum]
                if (og.get("goals_for") != new_game.get("goals_for") or
                        og.get("goals_against") != new_game.get("goals_against")):
                    changes.append(
                        f"  {team_raw}: game #{gnum} score changed "
                        f"{og.get('goals_for')}-{og.get('goals_against')} → "
                        f"{new_game.get('goals_for')}-{new_game.get('goals_against')}"
                    )

        # Detect standings changes
        if old_team:
            for field in ("wins", "losses", "draws", "points"):
                ov, nv = old_team.get(field), new_team.get(field)
                if ov != nv:
                    changes.append(f"  {team_raw}: {field} {ov} → {nv}")
        else:
            changes.append(f"  {team_raw}: new team (first appearance)")

        # Union of games: new wins on conflict, old preserved if missing from new
        merged_games = {**old_games, **new_games}
        merged_team = {**new_team, "games": sorted(merged_games.values(), key=lambda g: g["game_number"])}
        merged_teams.append(merged_team)

    # Report teams that disappeared (shouldn't happen, but flag it)
    for team_raw in old_teams_by_key:
        if team_raw not in new_teams_by_key:
            changes.append(f"  {team_raw}: REMOVED from fresh scrape (keeping old data)")
            old_team = old_teams_by_key[team_raw]
            old_games = old_game_index.get(team_raw, {})
            merged_team = {**old_team, "games": sorted(old_games.values(), key=lambda g: g["game_number"])}
            merged_teams.append(merged_team)

    merged = {**new, "teams": merged_teams}
    return merged, changes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--standings-dir", default="./standings", help="Directory with standings JSON files")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    standings_dir = Path(args.standings_dir)
    if not standings_dir.exists():
        sys.exit(f"Standings directory not found: {standings_dir}")

    json_files = sorted(standings_dir.glob("*.json"))
    if not json_files:
        sys.exit(f"No JSON files found in {standings_dir}")

    total_changes = 0
    new_divisions: list[str] = []
    changed_divisions: list[str] = []

    for path in json_files:
        division = path.stem
        try:
            new_data = json.loads(path.read_text())
        except json.JSONDecodeError:
            log.warning("Skipping malformed file: %s", path)
            continue

        old_data = _git_show(path)

        if old_data is None:
            # Brand-new division — nothing to merge, just keep fresh data
            new_divisions.append(division)
            print(f"[NEW] {division}: {len(new_data.get('teams', []))} teams")
            continue

        merged, changes = merge_division(old_data, new_data)

        if changes:
            changed_divisions.append(division)
            total_changes += len(changes)
            print(f"[CHANGED] {division} ({len(changes)} change(s)):")
            for line in changes:
                print(line)
            path.write_text(json.dumps(merged, indent=2, sort_keys=True))
        else:
            # Even if nothing changed logically, update scraped_at only if
            # underlying data actually differs from committed version
            if json.dumps(old_data, sort_keys=True) != json.dumps(new_data, sort_keys=True):
                # scraped_at timestamp changed but no real data diff — still write merged
                path.write_text(json.dumps(merged, indent=2, sort_keys=True))
            log.info("[unchanged] %s", division)

    print()
    print("=" * 60)
    print(f"New divisions:     {len(new_divisions)}")
    print(f"Changed divisions: {len(changed_divisions)}")
    print(f"Total changes:     {total_changes}")

    if new_divisions:
        print(f"\nNew: {', '.join(new_divisions)}")
    if changed_divisions:
        print(f"\nChanged: {', '.join(changed_divisions)}")


if __name__ == "__main__":
    main()
