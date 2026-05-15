"""
schedule_parser.py — Parse NCSA gameSchedule.cfm HTML into structured schedule data.

Pure module: HTML in, Python dicts out. No network, no file I/O.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Optional


@dataclass
class ScheduledGame:
    game_id: str
    division: str
    date: str           # ISO date, e.g. "2026-03-29"
    time: str           # 12-hour as on site, e.g. "04:15 PM"
    home_team: str      # raw team name, e.g. "SaddleBR-B13E-Morales"
    away_team: str      # raw team name
    field: str          # full field name from data-field
    home_score: Optional[int]   # None if not yet played
    away_score: Optional[int]

    @property
    def is_upcoming(self) -> bool:
        return self.home_score is None

    def home_club(self) -> str:
        return _parse_club(self.home_team)

    def away_club(self) -> str:
        return _parse_club(self.away_team)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["is_upcoming"] = self.is_upcoming
        d["home_club"] = self.home_club()
        d["away_club"] = self.away_club()
        return d


@dataclass
class DivisionSchedule:
    division: str
    scraped_at: str
    source_url: str
    games: list[ScheduledGame]

    def to_dict(self) -> dict[str, Any]:
        return {
            "division": self.division,
            "scraped_at": self.scraped_at,
            "source_url": self.source_url,
            "games": [g.to_dict() for g in self.games],
        }


def _parse_club(raw: str) -> str:
    """Extract the club name from 'Club-Division-Coach' format."""
    raw = raw.strip()
    parts = [p.strip() for p in raw.split("-")]
    return parts[0] if parts else raw


def _parse_date(mmddyy: str) -> str:
    """Convert 'MM/DD/YY' or 'MM/DD/YYYY' to ISO 'YYYY-MM-DD'. Returns original on failure."""
    s = mmddyy.strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return s


def _strip_label(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _cell_text(td) -> str:
    cell = td.__copy__()
    for span in cell.find_all("span", class_="mobile_only"):
        span.decompose()
    return _strip_label(cell.get_text(" ", strip=True))


def _parse_score(text: str) -> Optional[int]:
    text = text.strip()
    if text == "" or text == "-":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_schedule(html: str, division: str, source_url: str = "") -> DivisionSchedule:
    """
    Parse a full gameSchedule.cfm HTML response for one division.
    Primary data source: <button class="calendar_trigger"> data attributes.
    Scores come from td.game_home_score / td.game_visitor_score cells.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="schedule_table")
    if not table:
        raise ValueError("No schedule_table found in HTML")

    games: list[ScheduledGame] = []
    tbody = table.find("tbody") or table
    row_bgs = {"#FFFFFF", "#FBFBFB", "#ffffff", "#fbfbfb"}

    for tr in tbody.find_all("tr"):
        bg = (tr.get("bgcolor") or "").strip()
        if bg not in row_bgs:
            continue

        btn = tr.find("button", class_="calendar_trigger")
        if not btn:
            continue

        game_id = btn.get("data-game-id", "").strip()
        raw_date = btn.get("data-date", "").strip()
        game_time = btn.get("data-time", "").strip()
        field = btn.get("data-field", "").strip()
        home_team = btn.get("data-home-team", "").strip()
        away_team = btn.get("data-away-team", "").strip()

        if not game_id:
            continue

        # Scores from td cells (more reliable than button attrs for played games)
        home_score_td = tr.find("td", class_="game_home_score")
        away_score_td = tr.find("td", class_="game_visitor_score")

        home_score = _parse_score(_cell_text(home_score_td)) if home_score_td else None
        away_score = _parse_score(_cell_text(away_score_td)) if away_score_td else None

        # Division from td if available, else use the argument
        div_td = tr.find("td", class_="game_division")
        game_division = _cell_text(div_td) if div_td else division

        games.append(ScheduledGame(
            game_id=game_id,
            division=game_division,
            date=_parse_date(raw_date),
            time=game_time,
            home_team=home_team,
            away_team=away_team,
            field=field,
            home_score=home_score,
            away_score=away_score,
        ))

    return DivisionSchedule(
        division=division,
        scraped_at=datetime.utcnow().isoformat() + "Z",
        source_url=source_url,
        games=games,
    )
