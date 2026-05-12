"""
Extract just the team names from a standings page, without parsing all the
game-by-game data. Used by the index-builder when we hit all ~160 divisions
and only need to know which teams are in each.
"""
from __future__ import annotations

from bs4 import BeautifulSoup


def extract_team_names(html: str) -> list[str]:
    """
    Return a list of team-raw-strings (e.g. 'Tenafly-B12B-Schwartzberg') from
    a standings.cfm response. Returns [] if no standings table is present
    (e.g. division not yet flighted, empty division).
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="standings_table")
    if not table:
        return []
    teams: list[str] = []
    for tr in table.find_all("tr", class_="standings_row"):
        td = tr.find("td", class_="team_column")
        if td:
            name = td.get_text(strip=True)
            if name:
                teams.append(name)
    return teams
