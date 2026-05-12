"""Run the parser against the saved B12B fixture and pretty-print the result."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parser import parse_standings

fixture_path = Path(__file__).parent / "fixtures" / "b12b_table.html"
html = fixture_path.read_text()

result = parse_standings(html, division="B12B", source_url="https://www.ncsanj.com/standings.cfm")
data = result.to_dict()

# Sanity-check the standings table
print("=" * 60)
print(f"DIVISION: {data['division']}    Scraped: {data['scraped_at']}")
print("=" * 60)
print(f"{'#':>2}  {'Club':<14}  {'GP':>3}  {'W':>2}  {'L':>2}  {'D':>2}  {'Pts':>3}  {'GF':>3}  {'GA':>3}  {'GD':>4}  Form")
print("-" * 70)
for i, team in enumerate(data["teams"], 1):
    print(
        f"{i:>2}. {team['club']:<14}  "
        f"{team['played']:>3}  {team['wins']:>2}  {team['losses']:>2}  {team['draws']:>2}  "
        f"{team['points']:>3}  {team['goals_for']:>3}  {team['goals_against']:>3}  "
        f"{team['goal_diff']:>+4}  {team['form']}"
    )

# Spot-check one team's game-by-game results
print("\n" + "=" * 60)
print(f"GAMES FOR: {data['teams'][0]['club']} ({data['teams'][0]['team_raw']})")
print("=" * 60)
for g in data["teams"][0]["games"]:
    print(f"  {g['date']}  {g['time']:<9}  {g['result']}  {g['goals_for']}-{g['goals_against']}  "
          f"vs {g['opponent_club']:<14}  @ {g['venue_code']}")

# Validation invariants
print("\n" + "=" * 60)
print("VALIDATION")
print("=" * 60)
problems = []
for team in data["teams"]:
    derived = team["wins"] * 3 + team["draws"]
    if derived != team["points"]:
        problems.append(f"  {team['club']}: points={team['points']} but 3W+D={derived}")
    if team["wins"] + team["losses"] + team["draws"] != team["played"]:
        problems.append(f"  {team['club']}: W+L+D != played")
    sum_gf = sum(g["goals_for"] for g in team["games"])
    sum_ga = sum(g["goals_against"] for g in team["games"])
    if sum_gf != team["goals_for"]:
        problems.append(f"  {team['club']}: standings GF={team['goals_for']} but games sum to {sum_gf}")
    if sum_ga != team["goals_against"]:
        problems.append(f"  {team['club']}: standings GA={team['goals_against']} but games sum to {sum_ga}")

if not problems:
    print("All teams pass: 3W+D=Pts, W+L+D=GP, game-by-game GF/GA sums match standings totals.")
else:
    print("Issues found:")
    for p in problems:
        print(p)

# Dump the JSON the frontend would consume
out_path = Path(__file__).parent / "fixtures" / "b12b_output.json"
out_path.write_text(json.dumps(data, indent=2))
print(f"\nFull JSON written to: {out_path}")
print(f"JSON size: {out_path.stat().st_size:,} bytes")
