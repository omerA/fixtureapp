"""
parser.py — Parse NCSA standings HTML into clean Python dicts.

This module is pure: it takes an HTML string and returns structured data.
No network. No file I/O. That's deliberate — parsers should be testable
without the internet.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class Game:
    """One game in a team's results table."""
    game_number: str         # NCSA's game ID, e.g. "407789"
    opponent_raw: str        # full string as displayed, e.g. "Secaucus-B12B-Yahiax"
    opponent_club: str       # parsed club, e.g. "Secaucus"
    venue_code: str          # field code after the @, e.g. "SECAU-CountyShetikFl"
    date: str                # ISO date, "2026-03-29" (normalized from "03/29/26")
    time: str                # 12-hour as on site, "04:15 PM"
    goals_for: int
    goals_against: int

    @property
    def result(self) -> str:
        """Single-letter result code: W / L / D."""
        if self.goals_for > self.goals_against:
            return "W"
        if self.goals_for < self.goals_against:
            return "L"
        return "D"


@dataclass
class TeamStanding:
    """One row in the standings table, plus that team's game-by-game results."""
    team_raw: str            # full string, e.g. "WayneBG-B12B-Sanchez"
    club: str                # parsed club, e.g. "WayneBG"
    coach: str               # parsed coach, e.g. "Sanchez"
    played: int
    wins: int
    losses: int
    draws: int
    points: int
    goals_for: int
    goals_against: int
    games: list[Game]

    @property
    def goal_diff(self) -> int:
        return self.goals_for - self.goals_against

    @property
    def form(self) -> str:
        """Last 5 results, oldest to newest, as a string like 'WWLDW'."""
        sorted_games = sorted(self.games, key=lambda g: g.date)
        return "".join(g.result for g in sorted_games[-5:])


@dataclass
class DivisionStandings:
    division: str             # e.g. "B12B"
    scraped_at: str           # ISO datetime UTC
    source_url: str
    teams: list[TeamStanding]

    def to_dict(self) -> dict[str, Any]:
        return {
            "division": self.division,
            "scraped_at": self.scraped_at,
            "source_url": self.source_url,
            "teams": [
                {
                    **asdict(team),
                    "goal_diff": team.goal_diff,
                    "form": team.form,
                    "games": [
                        {**asdict(g), "result": g.result} for g in team.games
                    ],
                }
                for team in self.teams
            ],
        }


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_team_name(raw: str) -> tuple[str, str]:
    """
    NCSA team names follow 'Club-Flight-Coach' (or sometimes with a space).
    Returns (club, coach). Falls back gracefully on weird formats.
    """
    raw = raw.strip()
    # Some entries have stray whitespace like "Tenafly- B12B-Schwartzberg"
    parts = [p.strip() for p in raw.split("-")]
    if len(parts) >= 3:
        return parts[0], parts[-1]
    return raw, ""


def _parse_date(mmddyy: str) -> str:
    """Convert NCSA's '03/29/26' to ISO '2026-03-29'. Returns '' on failure."""
    mmddyy = mmddyy.strip()
    try:
        return datetime.strptime(mmddyy, "%m/%d/%y").date().isoformat()
    except ValueError:
        return mmddyy  # keep original if it doesn't match


def _strip_label(text: str) -> str:
    """
    NCSA wraps mobile labels inline, e.g. 'Date: 03/29/26'. The label is
    always a span we've already removed, but trailing whitespace and
    non-breaking spaces remain. Clean it up.
    """
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _parse_opponent_cell(cell_text: str) -> tuple[str, str]:
    """
    Parse 'vs. Secaucus-B12B-Yahiax @ SECAU-CountyShetikFl' into
    (opponent, venue). Tolerant of missing '@'.
    """
    txt = _strip_label(cell_text)
    # Strip leading "Opponent:" if a label span sneaks through
    txt = re.sub(r"^Opponent:\s*", "", txt, flags=re.IGNORECASE)
    # Strip leading "vs."
    txt = re.sub(r"^vs\.?\s*", "", txt, flags=re.IGNORECASE)
    if " @ " in txt:
        opp, venue = txt.split(" @ ", 1)
        return opp.strip(), venue.strip()
    return txt.strip(), ""


def _cell_value(td) -> str:
    """
    Extract the meaningful value from a results-table cell. The cell has a
    hidden mobile_only span ('Date:') that BeautifulSoup includes by default.
    We strip those out by removing all <span class='mobile_only'>.
    """
    cell = td.__copy__()
    for span in cell.find_all("span", class_="mobile_only"):
        span.decompose()
    return _strip_label(cell.get_text(" ", strip=True))


def _looks_like_standings_row(tr) -> bool:
    """The standings row has the team name in a td.team_column."""
    return bool(tr.find("td", class_="team_column"))


def _looks_like_results_row(tr) -> bool:
    """The hidden game-by-game row contains a nested .results_table."""
    return bool(tr.find("table", class_=re.compile(r"results_table")))


def _parse_games(results_tr, _bs4) -> list[Game]:
    """Parse the hidden expandable row into a list of Game objects."""
    games: list[Game] = []
    results_table = results_tr.find("table", class_=re.compile(r"results_table"))
    if not results_table:
        return games

    for row in results_table.find_all("tr", class_="clearfix"):
        opp_td = row.find("td", class_="game_opponent")
        num_td = row.find("td", class_="game_number")
        date_td = row.find("td", class_="game_date")
        time_td = row.find("td", class_="game_time")
        gf_td = row.find("td", class_="game_goals_for")
        ga_td = row.find("td", class_="game_goals_against")

        if not all([opp_td, num_td, date_td, time_td, gf_td, ga_td]):
            continue  # skip malformed row rather than crash

        opp_text = _cell_value(opp_td)
        opponent_raw, venue = _parse_opponent_cell(opp_text)
        club, _ = _parse_team_name(opponent_raw)

        try:
            gf = int(_cell_value(gf_td))
            ga = int(_cell_value(ga_td))
        except ValueError:
            continue  # game without recorded score yet

        games.append(Game(
            game_number=_cell_value(num_td),
            opponent_raw=opponent_raw,
            opponent_club=club,
            venue_code=venue,
            date=_parse_date(_cell_value(date_td)),
            time=_cell_value(time_td),
            goals_for=gf,
            goals_against=ga,
        ))
    return games


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_standings(html: str, division: str, source_url: str = "") -> DivisionStandings:
    """
    Parse a full standings.cfm HTML response into a DivisionStandings.
    `html` can be the whole page or just the #standings_table snippet.
    """
    from bs4 import BeautifulSoup  # local import keeps top of file dependency-light
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table", id="standings_table") or soup.find("table")
    if not table:
        raise ValueError("No standings_table found in HTML")

    teams: list[TeamStanding] = []
    rows = table.find("tbody").find_all("tr", recursive=False) if table.find("tbody") else table.find_all("tr", recursive=False)

    pending_standing: TeamStanding | None = None
    for tr in rows:
        if _looks_like_standings_row(tr):
            # flush previous team if it had no expandable row (shouldn't happen, but safe)
            if pending_standing is not None:
                teams.append(pending_standing)

            tds = tr.find_all("td", recursive=False)
            if len(tds) < 8:
                pending_standing = None
                continue

            team_raw = tds[0].get_text(strip=True)
            club, coach = _parse_team_name(team_raw)
            try:
                played = int(tds[1].get_text(strip=True))
                wins   = int(tds[2].get_text(strip=True))
                losses = int(tds[3].get_text(strip=True))
                draws  = int(tds[4].get_text(strip=True))
                points = int(tds[5].get_text(strip=True))
                gf     = int(tds[6].get_text(strip=True))
                ga     = int(tds[7].get_text(strip=True))
            except ValueError:
                pending_standing = None
                continue

            pending_standing = TeamStanding(
                team_raw=team_raw, club=club, coach=coach,
                played=played, wins=wins, losses=losses, draws=draws,
                points=points, goals_for=gf, goals_against=ga, games=[],
            )

        elif _looks_like_results_row(tr) and pending_standing is not None:
            pending_standing.games = _parse_games(tr, None)
            teams.append(pending_standing)
            pending_standing = None

    if pending_standing is not None:
        teams.append(pending_standing)

    return DivisionStandings(
        division=division,
        scraped_at=datetime.utcnow().isoformat() + "Z",
        source_url=source_url,
        teams=teams,
    )
