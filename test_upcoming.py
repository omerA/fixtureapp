"""
test_upcoming.py — The cross-team "Upcoming games" page and the field details
the schedule parser keeps for it.

Run:
    python -m pytest -q test_upcoming.py
"""
from __future__ import annotations

import json
import re
from datetime import timedelta

# Shares the throwaway database and app client set up by the rollover tests
from test_season_rollover import _follow, _register, app_client, client  # noqa: F401
from app import main
from schedule_parser import parse_schedule

KIM = "Tenafly-B12A-Kim"
LEE = "Tenafly-B13B-Lee"
PARK = "Cresskill-B13A-Park"
SCHWARTZBERG = "Tenafly-B13A-Schwartzberg"


def _day(offset: int) -> str:
    return (main._today() + timedelta(days=offset)).isoformat()


def _game(game_id, division, date, time, home, away, field_id="", field="Some Field", played=False):
    return {
        "game_id": game_id, "division": division, "date": date, "time": time,
        "home_team": home, "away_team": away, "field": field, "field_id": field_id,
        "home_score": 1 if played else None, "away_score": 0 if played else None,
        "is_upcoming": not played,
    }


def _write_schedule(tmp_path, division, games, fields=None):
    data = {"division": division, "games": games}
    if fields is not None:
        data["fields"] = fields
    (tmp_path / f"{division}.json").write_text(json.dumps(data), encoding="utf-8")


def _rows(html: str) -> list[tuple[str, str, str]]:
    """(game id, kickoff, warm-up) for each game row, in page order."""
    return re.findall(
        r'data-game="([^"]+)".*?data-kickoff>([^<]+)<.*?data-arrive[^>]*>([^<]+)<', html, re.S)


# ---------------------------------------------------------------------------
# /upcoming
# ---------------------------------------------------------------------------

def test_games_from_all_teams_in_kickoff_order_with_warmup(client, tmp_path):
    uid = _register(client, "a@example.com")
    _follow(uid, KIM)
    _follow(uid, LEE)
    _write_schedule(tmp_path, "B12A", [
        _game("1", "B12A", _day(3), "04:45 PM", KIM, "Ajax-B12A-Smith"),
        _game("2", "B12A", _day(1), "12:15 PM", "Ajax-B12A-Smith", KIM),
        _game("3", "B12A", _day(-7), "09:00 AM", KIM, "Ajax-B12A-Smith", played=True),
        _game("4", "B12A", _day(2), "09:00 AM", "Ajax-B12A-Smith", "Nutley-B12A-Jones"),
    ])
    _write_schedule(tmp_path, "B13B", [
        _game("5", "B13B", _day(3), "10:00 AM", "Ramsey-B13B-Diaz", LEE),
    ])

    resp = client.get("/upcoming")

    assert resp.status_code == 200
    # Day order, then clock order within a day: 10:00 AM comes before 04:45 PM.
    # The played game and the game between two other teams are left out.
    assert _rows(resp.text) == [
        ("2", "12:15 PM", "11:45 AM"),
        ("5", "10:00 AM", "9:30 AM"),
        ("1", "4:45 PM", "4:15 PM"),
    ]
    assert re.findall(r'data-day="([^"]+)"', resp.text) == [_day(1), _day(3)]
    assert "Tomorrow" in resp.text
    assert "vs Ramsey" in resp.text


def test_location_shows_address_with_map_link(client, tmp_path):
    uid = _register(client, "a@example.com")
    _follow(uid, KIM)
    _write_schedule(tmp_path, "B12A", [
        _game("1", "B12A", _day(2), "10:00 AM", KIM, "Ajax-B12A-Smith",
              field_id="18", field="Municipal Field"),
    ], fields={"18": {"name": "Municipal Field", "address": "100 Riveredge Rd, Tenafly, NJ 07670",
                      "details": "LIGHTS — ARTIFICIAL", "size": "", "comments": ""}})

    html = client.get("/upcoming").text

    assert "Municipal Field" in html
    assert "100 Riveredge Rd, Tenafly, NJ 07670" in html
    assert "https://www.google.com/maps/search/?api=1&amp;query=100+Riveredge+Rd%2C+Tenafly%2C+NJ+07670" in html
    assert "LIGHTS — ARTIFICIAL" in html


def test_schedule_file_without_field_details_still_renders(client, tmp_path):
    # Files scraped before field details were kept have no "fields" or "field_id"
    uid = _register(client, "a@example.com")
    _follow(uid, KIM)
    game = _game("1", "B12A", _day(2), "10:00 AM", KIM, "Ajax-B12A-Smith", field="Municipal Field")
    del game["field_id"]
    _write_schedule(tmp_path, "B12A", [game])

    html = client.get("/upcoming").text

    assert "Municipal Field" in html
    assert "data-address" not in html


def test_game_between_two_followed_teams_is_listed_once(client, tmp_path):
    uid = _register(client, "a@example.com")
    _follow(uid, PARK)
    _follow(uid, SCHWARTZBERG)
    _write_schedule(tmp_path, "B13A", [
        _game("9", "B13A", _day(4), "11:00 AM", PARK, SCHWARTZBERG),
    ])

    html = client.get("/upcoming").text

    assert html.count('data-game="9"') == 1
    assert "You also follow" in html


def test_postponed_games_are_listed_separately(client, tmp_path):
    uid = _register(client, "a@example.com")
    _follow(uid, KIM)
    _write_schedule(tmp_path, "B12A", [
        _game("1", "B12A", _day(-3), "10:00 AM", KIM, "Ajax-B12A-Smith"),
        _game("2", "B12A", _day(5), "10:00 AM", KIM, "Nutley-B12A-Jones", field="To Be Scheduled"),
    ])

    html = client.get("/upcoming").text

    assert _rows(html) == []
    assert html.count("Postponed") == 2


def test_orphaned_team_is_skipped_and_points_to_repick(client, tmp_path):
    uid = _register(client, "a@example.com")
    _follow(uid, KIM)
    _follow(uid, "Tenafly-B12B-Schwartzberg")   # last season, not in the index
    _write_schedule(tmp_path, "B12A", [_game("1", "B12A", _day(2), "10:00 AM", KIM, "Ajax-B12A-Smith")])
    _write_schedule(tmp_path, "B12B", [
        _game("2", "B12B", _day(2), "11:00 AM", "Tenafly-B12B-Schwartzberg", "Ajax-B12B-Smith"),
    ])

    html = client.get("/upcoming").text

    assert [r[0] for r in _rows(html)] == ["1"]
    assert "need to be picked again" in html


def test_no_schedule_data_shows_empty_state(client):
    uid = _register(client, "a@example.com")
    _follow(uid, KIM)

    resp = client.get("/upcoming")

    assert resp.status_code == 200
    assert "No upcoming games found" in resp.text


def test_requires_login_and_a_followed_team(client):
    resp = client.get("/upcoming", follow_redirects=False)
    assert (resp.status_code, resp.headers["location"]) == (302, "/login")

    _register(client, "a@example.com")
    resp = client.get("/upcoming", follow_redirects=False)
    assert (resp.status_code, resp.headers["location"]) == (302, "/onboard")


def test_only_the_current_users_teams_are_shown(client, tmp_path):
    other = _register(client, "other@example.com")
    _follow(other, LEE)
    client.cookies.clear()
    uid = _register(client, "a@example.com")
    _follow(uid, KIM)
    _write_schedule(tmp_path, "B12A", [_game("1", "B12A", _day(2), "10:00 AM", KIM, "Ajax-B12A-Smith")])
    _write_schedule(tmp_path, "B13B", [_game("5", "B13B", _day(2), "10:00 AM", "Ramsey-B13B-Diaz", LEE)])

    assert [r[0] for r in _rows(client.get("/upcoming").text)] == ["1"]


# ---------------------------------------------------------------------------
# Team renamed on the schedule page before the standings page
# ---------------------------------------------------------------------------

def _write_standings(tmp_path, monkeypatch, division, team_names):
    # The client fixture points standings and schedules at the same folder
    folder = tmp_path / "standings"
    folder.mkdir(exist_ok=True)
    monkeypatch.setattr(main, "STANDINGS_DIR", folder)
    stats = {"played": 0, "wins": 0, "losses": 0, "draws": 0, "points": 0,
             "goals_for": 0, "goals_against": 0, "goal_diff": 0, "form": "", "games": []}
    teams = [{"team_raw": n, "club": n.split("-")[0], "coach": n.split("-")[-1], **stats}
             for n in team_names]
    (folder / f"{division}.json").write_text(
        json.dumps({"division": division, "teams": teams}), encoding="utf-8")


def test_team_renamed_on_the_schedule_still_gets_its_games(client, tmp_path, monkeypatch):
    uid = _register(client, "a@example.com")
    _follow(uid, KIM)
    _write_standings(tmp_path, monkeypatch, "B12A", [KIM, "Ajax-B12A-Smith", "Nutley-B12A-Jones"])
    _write_schedule(tmp_path, "B12A", [
        _game("1", "B12A", _day(2), "10:00 AM", "Tenafly-B12A-Newcoach", "Ajax-B12A-Smith"),
        _game("2", "B12A", _day(3), "11:00 AM", "Nutley-B12A-Jones", "Tenafly-B12A-Newcoach"),
        _game("3", "B12A", _day(4), "09:00 AM", "Ajax-B12A-Smith", "Nutley-B12A-Jones"),
    ])

    html = client.get("/upcoming").text

    assert [r[0] for r in _rows(html)] == ["1", "2"]
    assert "vs Ajax" in html and "vs Nutley" in html
    assert "vs Tenafly" not in html   # the team is never its own opponent
    # The team page reads the same schedule
    assert "vs Ajax" in client.get(f"/team/{KIM}").text


def test_renamed_team_shows_new_name_and_announces_it(client, tmp_path, monkeypatch):
    uid = _register(client, "a@example.com")
    _follow(uid, KIM)
    _follow(uid, LEE)
    _write_standings(tmp_path, monkeypatch, "B12A", [KIM, "Ajax-B12A-Smith"])
    _write_schedule(tmp_path, "B12A", [
        _game("1", "B12A", _day(2), "10:00 AM", "Tenafly-B12A-Newcoach", "Ajax-B12A-Smith"),
    ])

    for path in ("/dashboard", f"/team/{KIM}", "/upcoming"):
        html = client.get(path).text
        announced = json.loads(re.search(
            r'<script type="application/json" id="fi-rename-data">(.*?)</script>', html, re.S).group(1))
        assert [(r["id"], r["old_title"], r["new_title"]) for r in announced] == [
            (f"{KIM}>Tenafly-B12A-Newcoach", "BU12-Kim", "BU12-Newcoach"),
        ], path
        # The page itself already uses the new name; the old one lives only in the announcement
        page = html.split('id="fi-rename"')[0]
        assert "BU12-Newcoach" in page and "BU12-Kim" not in page, path

    # A team that was not renamed gets no announcement
    assert "fi-rename" not in client.get(f"/team/{LEE}").text


def test_rename_is_not_guessed_when_two_names_could_match(client, tmp_path, monkeypatch):
    uid = _register(client, "a@example.com")
    _follow(uid, KIM)
    _write_standings(tmp_path, monkeypatch, "B12A", [KIM, "Ajax-B12A-Smith"])
    _write_schedule(tmp_path, "B12A", [
        _game("1", "B12A", _day(2), "10:00 AM", "Tenafly-B12A-Newcoach", "Ajax-B12A-Smith"),
        _game("2", "B12A", _day(3), "11:00 AM", "Tenafly-B12A-Other", "Ajax-B12A-Smith"),
    ])

    assert _rows(client.get("/upcoming").text) == []


def test_another_team_from_the_same_club_is_not_mistaken_for_a_rename(client, tmp_path, monkeypatch):
    uid = _register(client, "a@example.com")
    _follow(uid, KIM)
    # A second Tenafly team that the standings do know: its games are its own
    _write_standings(tmp_path, monkeypatch, "B12A", [KIM, "Tenafly-B12A-Second", "Ajax-B12A-Smith"])
    _write_schedule(tmp_path, "B12A", [
        _game("1", "B12A", _day(2), "10:00 AM", "Tenafly-B12A-Second", "Ajax-B12A-Smith"),
    ])

    assert _rows(client.get("/upcoming").text) == []


# ---------------------------------------------------------------------------
# schedule_parser: field details
# ---------------------------------------------------------------------------

def _row(game_id, field_id, field, more_info=""):
    return f"""
    <tr bgcolor="#FFFFFF">
      <td class="add_calendar"><button class="calendar_trigger" data-field-id="{field_id}"
          data-game-id="{game_id}" data-date="11/22/2026" data-time="10:00 AM" data-field="{field}"
          data-home-team="Spartan-B12A-McCormack" data-away-team="Hotspur-B12A-Rotolo"></button></td>
      <td class="game_division"><span class="mobile_only">Division:</span> B12A</td>
      <td class="game_field"><a class="more_link" href="#">PAR-X</a>{more_info}</td>
      <td class="game_home_score"></td><td class="game_visitor_score"></td>
    </tr>"""


MORE_INFO = """
<div class="more_info"><div class="container"><style>.x { color: red; }</style>
<ul class="more_info_list">
  <li class="field_name"><span class="title">Field:</span> Parkway Middle School 9
      <A Target="Map" href="//maps.google.com/maps?q=145">map it</A></li>
  <li class="field_name"><span class="title">Field Details:</span> NO-LIGHTS &mdash; GRASS</li>
  <li class="field_address"><span class="title">Address:</span> 145 E. Ridgewood Avenue<br> Paramus, NJ 07652</li>
  <li class="field_size"><span class="title">Field Size:</span> Large Field (11 vs 11)</li>
  <li class="field_comments"><span class="title">Comments:</span> 9 v 9 ONLY</li>
  <li class="field_directions"><span class="title">Directions:</span> Take Route 17 North.</li>
</ul></div></div>"""


def test_parser_keeps_field_id_and_field_details():
    html = ('<table id="schedule_table"><tbody>'
            + _row("1", "902", "Parkway Middle School 9", MORE_INFO)
            + _row("2", "902", "Parkway Middle School 9", MORE_INFO)
            + _row("3", "", "Mystery Field")
            + '</tbody></table>')

    data = parse_schedule(html, "B12A").to_dict()

    assert [g["field_id"] for g in data["games"]] == ["902", "902", ""]
    assert data["fields"] == {"902": {
        "name": "Parkway Middle School 9",
        "address": "145 E. Ridgewood Avenue, Paramus, NJ 07652",
        "details": "NO-LIGHTS — GRASS",
        "size": "Large Field (11 vs 11)",
        "comments": "9 v 9 ONLY",
    }}


def test_parser_tolerates_a_row_without_the_field_popup():
    html = '<table id="schedule_table"><tbody>' + _row("1", "77", "Bare Field") + '</tbody></table>'

    data = parse_schedule(html, "B12A").to_dict()

    assert data["fields"]["77"] == {"name": "Bare Field", "address": "", "details": "", "size": "", "comments": ""}
