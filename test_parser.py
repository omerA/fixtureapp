"""Test the parser against the saved B12B fixture."""
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from parser import parse_standings


@pytest.fixture
def b12b_html():
    """Load the B12B fixture HTML."""
    fixture_path = Path(__file__).parent / "fixtures" / "b12b_table.html"
    return fixture_path.read_text(encoding="utf-8")


def test_parse_standings_returns_teams(b12b_html):
    """At least one team should be parsed."""
    result = parse_standings(b12b_html, division="B12B", source_url="https://www.ncsanj.com/standings.cfm")
    assert len(result.teams) > 0, "Expected at least one team to be parsed"


def test_points_calculation(b12b_html):
    """For every team, wins*3 + draws should equal points."""
    result = parse_standings(b12b_html, division="B12B", source_url="https://www.ncsanj.com/standings.cfm")
    for team in result.teams:
        derived = team.wins * 3 + team.draws
        assert derived == team.points, (
            f"Team {team.club}: points={team.points} but 3W+D={derived}"
        )


def test_games_played_calculation(b12b_html):
    """For every team, wins + losses + draws should equal games played."""
    result = parse_standings(b12b_html, division="B12B", source_url="https://www.ncsanj.com/standings.cfm")
    for team in result.teams:
        total = team.wins + team.losses + team.draws
        assert total == team.played, (
            f"Team {team.club}: W+L+D={total} but played={team.played}"
        )


@pytest.mark.xfail(
    strict=False,
    reason="WorldClassFC has mismatches: standings GF=11 but games sum to 13; standings GA=21 but games sum to 19. Needs investigation (possibly a forfeit or a site-side adjustment)."
)
def test_goals_match_game_sums(b12b_html):
    """
    Goals-for/against in standings should match the sum over game-by-game results.

    This test is marked xfail because the fixture has known mismatches that need investigation.
    """
    result = parse_standings(b12b_html, division="B12B", source_url="https://www.ncsanj.com/standings.cfm")
    data = result.to_dict()

    mismatches = []
    for team in data["teams"]:
        sum_gf = sum(g["goals_for"] for g in team["games"])
        sum_ga = sum(g["goals_against"] for g in team["games"])
        if sum_gf != team["goals_for"]:
            mismatches.append(
                f"  {team['club']}: standings GF={team['goals_for']} but games sum to {sum_gf}"
            )
        if sum_ga != team["goals_against"]:
            mismatches.append(
                f"  {team['club']}: standings GA={team['goals_against']} but games sum to {sum_ga}"
            )

    if mismatches:
        mismatch_text = "\n".join(mismatches)
        raise AssertionError(f"Goals totals mismatch:\n{mismatch_text}")
