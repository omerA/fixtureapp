"""
test_season_rollover.py — New-season handling.

Covers the app side (orphaned subscriptions: detection, re-pick suggestions,
replace/unfollow routes, archiving, /onboard) and the merge side
(merge_standings must not leak last season's teams or games into a division
code that is reused).

Run:
    python -m pytest -q test_season_rollover.py
"""
from __future__ import annotations

import copy
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# app/db.py picks its database from DATABASE_URL at import time, and the
# Alembic env reads the same variable when the app runs migrations on startup.
# Point both at a throwaway SQLite file *before* importing the app so the
# repo's app.db is never touched. check_same_thread=false because TestClient
# serves requests from a different thread than the one that opens connections.
_TMP_DIR = tempfile.mkdtemp(prefix="fixtureapp-test-")
_TEST_DB_URL = f"sqlite:///{Path(_TMP_DIR, 'test.db').as_posix()}?check_same_thread=false"
assert "app.db" not in sys.modules, "app.db was imported before the test database was configured"
os.environ["DATABASE_URL"] = _TEST_DB_URL

import sqlalchemy as sa  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as app_db  # noqa: E402
from app import main  # noqa: E402
from app.models import Subscription, User  # noqa: E402
from merge_standings import merge_division, season_of  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _index(team_keys: list[str], **extra) -> dict:
    """Build a team_index-shaped dict from 'Club-Division-Coach' keys."""
    by_team, by_club = {}, {}
    for key in team_keys:
        club, division, coach = key.split("-")
        by_team[key] = {"club": club, "division": division, "coach": coach}
        by_club.setdefault(club, []).append(key)
    return {"by_team": by_team, "by_club": by_club,
            "divisions": sorted({t["division"] for t in by_team.values()}), **extra}


# This season's teams. Deliberately listed in a different order from the
# expected suggestion order, so the test proves the sort.
NEW_SEASON = [
    "Tenafly-G13A-Schwartzberg",
    "Tenafly-B12A-Kim",
    "Tenafly-B14A-Schwartzberg",
    "Tenafly-B13B-Lee",
    "Tenafly-B13A-Schwartzberg",
    "Cresskill-B13A-Park",
]
OLD_TEAM = "Tenafly-B12B-Schwartzberg"   # last season; not in NEW_SEASON


# Session-scoped so other test modules can import and share it
@pytest.fixture(scope="session")
def app_client():
    assert Path(app_db.engine.url.database).parent == Path(_TMP_DIR), \
        "tests must not run against the repo's app.db"
    with TestClient(main.app) as c:   # runs migrations + loads the real index once
        yield c
    app_db.engine.dispose()
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


@pytest.fixture
def client(app_client, monkeypatch, tmp_path):
    """Logged-out client, empty database, index set to NEW_SEASON, no data files."""
    saved = dict(main._team_index)
    main._team_index.clear()
    main._team_index.update(_index(NEW_SEASON))
    monkeypatch.setattr(main, "STANDINGS_DIR", tmp_path)
    monkeypatch.setattr(main, "SCHEDULES_DIR", tmp_path)
    with app_db.SessionLocal() as db:
        db.query(Subscription).delete()
        db.query(User).delete()
        db.commit()
    app_client.cookies.clear()
    yield app_client
    main._team_index.clear()
    main._team_index.update(saved)


def _register(client: TestClient, email: str) -> int:
    """Create an account (which logs the client in) and return the user id."""
    resp = client.post("/register", data={"email": email, "password": "correct-horse"})
    assert resp.status_code == 200
    with app_db.SessionLocal() as db:
        return db.query(User).filter(User.email == email).one().id


def _follow(user_id: int, team_key: str, season: str | None = None) -> int:
    club, division, coach = team_key.split("-")
    with app_db.SessionLocal() as db:
        sub = Subscription(user_id=user_id, team_key=team_key, division=division,
                           club=club, coach=coach, season=season)
        db.add(sub)
        db.commit()
        return sub.id


def _subs(user_id: int) -> dict[int, tuple[str, str | None]]:
    """{subscription id: (team_key, season)} for a user."""
    with app_db.SessionLocal() as db:
        rows = db.query(Subscription).filter(Subscription.user_id == user_id).all()
        return {s.id: (s.team_key, s.season) for s in rows}


def _suggested(html: str) -> list[str]:
    return re.findall(r'data-suggestion="([^"]+)"', html)


# ---------------------------------------------------------------------------
# Dashboard: orphan detection + suggestions
# ---------------------------------------------------------------------------

def test_orphan_shown_with_same_club_suggestions_in_order(client):
    uid = _register(client, "a@example.com")
    orphan_id = _follow(uid, OLD_TEAM)
    _follow(uid, "Cresskill-B13A-Park")

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    html = resp.text

    assert "pick your teams again" in html or "pick your team again" in html
    assert "BU12-Schwartzberg" in html                      # what it was
    # Same gender first; then closest to old age + 1 (U13); then same coach.
    assert _suggested(html) == [
        "Tenafly-B13A-Schwartzberg",   # boys, U13, same coach
        "Tenafly-B13B-Lee",            # boys, U13
        "Tenafly-B14A-Schwartzberg",   # boys, one year off, same coach
        "Tenafly-B12A-Kim",            # boys, one year off
        "Tenafly-G13A-Schwartzberg",   # girls last
    ]
    assert f'action="/subscriptions/{orphan_id}/replace"' in html
    assert f'action="/subscriptions/{orphan_id}/unfollow"' in html
    assert f'href="/onboard?replace={orphan_id}"' in html
    # The valid team is still a normal card; the orphan is not linked as one.
    assert 'href="/team/Cresskill-B13A-Park"' in html
    assert f'href="/team/{OLD_TEAM}"' not in html


def test_spring_season_keeps_the_same_age_group(client):
    # Fall -> spring is the same playing year, so U12 stays the best match.
    main._team_index["season"] = "2027-spring"
    uid = _register(client, "a@example.com")
    _follow(uid, OLD_TEAM)
    assert _suggested(client.get("/dashboard").text)[0] == "Tenafly-B12A-Kim"


def test_suggestions_skip_teams_already_followed(client):
    uid = _register(client, "a@example.com")
    _follow(uid, OLD_TEAM)
    _follow(uid, "Tenafly-B13A-Schwartzberg")
    assert "Tenafly-B13A-Schwartzberg" not in _suggested(client.get("/dashboard").text)


def test_club_with_no_teams_offers_only_search_and_stop(client):
    uid = _register(client, "a@example.com")
    orphan_id = _follow(uid, "Dumont-B12B-Rossi")
    html = client.get("/dashboard").text
    assert _suggested(html) == []
    assert "/replace" not in html
    assert f'href="/onboard?replace={orphan_id}"' in html
    assert f'action="/subscriptions/{orphan_id}/unfollow"' in html


def test_all_orphaned_user_reaches_dashboard_without_redirect_loop(client):
    uid = _register(client, "a@example.com")
    _follow(uid, OLD_TEAM)
    resp = client.get("/dashboard", follow_redirects=False)
    assert resp.status_code == 200
    assert "BU12-Schwartzberg" in resp.text
    assert "not following any teams yet" not in resp.text
    assert client.get("/", follow_redirects=False).headers["location"] == "/dashboard"


@pytest.mark.parametrize("index", [{}, {"by_team": {}, "by_club": {}}])
def test_empty_index_marks_nothing_orphaned(client, index):
    main._team_index.clear()
    main._team_index.update(index)
    uid = _register(client, "a@example.com")
    _follow(uid, OLD_TEAM)
    resp = client.get("/dashboard", follow_redirects=False)
    assert resp.status_code == 200
    assert "New season" not in resp.text
    assert f'href="/team/{OLD_TEAM}"' in resp.text          # still a normal card
    assert client.get(f"/team/{OLD_TEAM}", follow_redirects=False).status_code == 200


def test_orphaned_team_pages_redirect_to_dashboard(client):
    uid = _register(client, "a@example.com")
    _follow(uid, OLD_TEAM)
    for url in (f"/team/{OLD_TEAM}", f"/team/{OLD_TEAM}/matchup"):
        resp = client.get(url, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/dashboard"


# ---------------------------------------------------------------------------
# Replace / stop following
# ---------------------------------------------------------------------------

def test_replace_swaps_exactly_that_subscription_and_archives_the_old_row(client):
    uid = _register(client, "a@example.com")
    orphan_id = _follow(uid, OLD_TEAM)
    other_orphan_id = _follow(uid, "Tenafly-G10C-Lopez")
    valid_id = _follow(uid, "Cresskill-B13A-Park")

    resp = client.post(f"/subscriptions/{orphan_id}/replace",
                       data={"team_key": "Tenafly-B13A-Schwartzberg"}, follow_redirects=False)
    assert resp.status_code == 302 and resp.headers["location"] == "/dashboard"

    subs = _subs(uid)
    # Old row is kept, marked as a past season (no index season -> generic label)
    assert subs.pop(orphan_id) == (OLD_TEAM, "previous")
    # Everything else is untouched
    assert subs.pop(other_orphan_id) == ("Tenafly-G10C-Lopez", None)
    assert subs.pop(valid_id) == ("Cresskill-B13A-Park", None)
    # Exactly one new, active row for the chosen team, filled from the index
    assert list(subs.values()) == [("Tenafly-B13A-Schwartzberg", None)]
    with app_db.SessionLocal() as db:
        new = db.get(Subscription, next(iter(subs)))
        assert (new.division, new.club, new.coach) == ("B13A", "Tenafly", "Schwartzberg")

    html = client.get("/dashboard").text
    assert 'href="/team/Tenafly-B13A-Schwartzberg"' in html
    assert "BU12-Schwartzberg" not in html                  # archived: gone from view
    assert "GU10-Lopez" in html                             # the other orphan still asks


@pytest.mark.parametrize("season, label", [
    ("2026-fall", "2026-spring"),
    ("2027-spring", "2026-fall"),
    ("garbage", "previous"),
])
def test_archived_row_is_labelled_with_the_previous_season(client, season, label):
    main._team_index["season"] = season
    uid = _register(client, "a@example.com")
    orphan_id = _follow(uid, OLD_TEAM)
    client.post(f"/subscriptions/{orphan_id}/replace", data={"team_key": "Tenafly-B13B-Lee"})
    assert _subs(uid)[orphan_id] == (OLD_TEAM, label)


def test_replace_with_a_team_already_followed_does_not_duplicate(client):
    uid = _register(client, "a@example.com")
    orphan_id = _follow(uid, OLD_TEAM)
    valid_id = _follow(uid, "Tenafly-B13A-Schwartzberg")
    resp = client.post(f"/subscriptions/{orphan_id}/replace",
                       data={"team_key": "Tenafly-B13A-Schwartzberg"})
    assert resp.status_code == 200
    assert _subs(uid) == {orphan_id: (OLD_TEAM, "previous"),
                          valid_id: ("Tenafly-B13A-Schwartzberg", None)}


def test_replace_rejects_a_team_that_is_not_in_the_index(client):
    uid = _register(client, "a@example.com")
    orphan_id = _follow(uid, OLD_TEAM)
    resp = client.post(f"/subscriptions/{orphan_id}/replace", data={"team_key": "Nowhere-B13A-Nobody"})
    assert resp.status_code == 400
    assert _subs(uid) == {orphan_id: (OLD_TEAM, None)}


def test_replace_leaves_a_valid_subscription_alone(client):
    uid = _register(client, "a@example.com")
    valid_id = _follow(uid, "Cresskill-B13A-Park")
    client.post(f"/subscriptions/{valid_id}/replace", data={"team_key": "Tenafly-B13B-Lee"})
    assert _subs(uid) == {valid_id: ("Cresskill-B13A-Park", None)}


def test_stop_following_removes_the_subscription(client):
    uid = _register(client, "a@example.com")
    orphan_id = _follow(uid, OLD_TEAM)
    valid_id = _follow(uid, "Cresskill-B13A-Park")
    resp = client.post(f"/subscriptions/{orphan_id}/unfollow", follow_redirects=False)
    assert resp.status_code == 302 and resp.headers["location"] == "/dashboard"
    assert _subs(uid) == {valid_id: ("Cresskill-B13A-Park", None)}   # a real delete
    assert "New season" not in client.get("/dashboard").text


def test_another_users_subscription_cannot_be_replaced_or_removed(client):
    victim = _register(client, "victim@example.com")
    orphan_id = _follow(victim, OLD_TEAM)

    attacker = TestClient(main.app)          # separate cookie jar; no lifespan re-run
    _register(attacker, "attacker@example.com")
    resp = attacker.post(f"/subscriptions/{orphan_id}/replace",
                         data={"team_key": "Tenafly-B13A-Schwartzberg"})
    assert resp.status_code == 404
    assert attacker.post(f"/subscriptions/{orphan_id}/unfollow").status_code == 404
    # /onboard's replace hint is ignored for someone else's row too
    attacker.post("/onboard", data={"teams": ["Tenafly-B13B-Lee"], "replace": str(orphan_id)})
    assert _subs(victim) == {orphan_id: (OLD_TEAM, None)}


def test_new_routes_require_login(client):
    uid = _register(client, "a@example.com")
    orphan_id = _follow(uid, OLD_TEAM)
    client.cookies.clear()
    for url, data in ((f"/subscriptions/{orphan_id}/replace", {"team_key": "Tenafly-B13B-Lee"}),
                      (f"/subscriptions/{orphan_id}/unfollow", {})):
        resp = client.post(url, data=data, follow_redirects=False)
        assert resp.status_code == 302 and resp.headers["location"] == "/login"
    assert _subs(uid) == {orphan_id: (OLD_TEAM, None)}


# ---------------------------------------------------------------------------
# Archived rows
# ---------------------------------------------------------------------------

def test_archived_rows_are_invisible(client):
    uid = _register(client, "a@example.com")
    _follow(uid, OLD_TEAM, season="2026-spring")
    # Archived under a key that exists again this season: still not a card
    _follow(uid, "Tenafly-B13B-Lee", season="2026-spring")
    _follow(uid, "Cresskill-B13A-Park")

    html = client.get("/dashboard").text
    assert 'href="/team/Cresskill-B13A-Park"' in html
    assert "New season" not in html
    assert "Schwartzberg" not in html and "BU13-Lee" not in html
    for url in ("/team/Tenafly-B13B-Lee", "/team/Tenafly-B13B-Lee/matchup"):
        assert client.get(url, follow_redirects=False).headers["location"] == "/dashboard"
    # ...and it is not preselected in the team picker
    assert "Tenafly-B13B-Lee" not in client.get("/onboard").text


def test_user_with_only_archived_rows_is_sent_to_onboarding(client):
    uid = _register(client, "a@example.com")
    _follow(uid, OLD_TEAM, season="2026-spring")
    resp = client.get("/dashboard", follow_redirects=False)
    assert resp.status_code == 302 and resp.headers["location"] == "/onboard"
    assert client.get("/onboard", follow_redirects=False).status_code == 200


def test_archived_row_does_not_block_following_the_same_key_again(client):
    uid = _register(client, "a@example.com")
    archived_id = _follow(uid, "Tenafly-B13B-Lee", season="2026-spring")
    client.post("/onboard", data={"teams": ["Tenafly-B13B-Lee"]})
    subs = _subs(uid)
    assert subs.pop(archived_id) == ("Tenafly-B13B-Lee", "2026-spring")
    assert list(subs.values()) == [("Tenafly-B13B-Lee", None)]
    # Two *active* rows for one team are still rejected by the database
    with pytest.raises(sa.exc.IntegrityError):
        _follow(uid, "Tenafly-B13B-Lee")


# ---------------------------------------------------------------------------
# /onboard
# ---------------------------------------------------------------------------

def test_onboard_post_leaves_orphaned_and_archived_rows_alone(client):
    uid = _register(client, "a@example.com")
    orphan_id = _follow(uid, OLD_TEAM)
    archived_id = _follow(uid, "Tenafly-G10C-Lopez", season="2026-spring")
    kept_id = _follow(uid, "Cresskill-B13A-Park")
    dropped_id = _follow(uid, "Tenafly-B12A-Kim")

    # The picker preselects this season's teams only
    page = client.get("/onboard").text
    assert "Cresskill-B13A-Park" in page and "Tenafly-B12A-Kim" in page
    assert OLD_TEAM not in page and "Tenafly-G10C-Lopez" not in page

    # Keep one, drop one, add one (submitted twice: must not trip uniqueness)
    resp = client.post("/onboard", follow_redirects=False, data={
        "teams": ["Cresskill-B13A-Park", "Tenafly-B13B-Lee", "Tenafly-B13B-Lee"]})
    assert resp.status_code == 302 and resp.headers["location"] == "/dashboard"

    subs = _subs(uid)
    assert subs.pop(orphan_id) == (OLD_TEAM, None)                      # still awaiting a re-pick
    assert subs.pop(archived_id) == ("Tenafly-G10C-Lopez", "2026-spring")
    assert subs.pop(kept_id) == ("Cresskill-B13A-Park", None)           # same row, not re-created
    assert dropped_id not in subs
    assert list(subs.values()) == [("Tenafly-B13B-Lee", None)]


def test_onboard_post_with_nothing_valid_changes_nothing(client):
    uid = _register(client, "a@example.com")
    orphan_id = _follow(uid, OLD_TEAM)
    valid_id = _follow(uid, "Cresskill-B13A-Park")
    before = _subs(uid)
    for teams in ([], [OLD_TEAM], ["Nowhere-B13A-Nobody"]):
        resp = client.post("/onboard", data={"teams": teams})
        assert "Select at least one team" in resp.text
    main._team_index.clear()                 # index failed to load
    client.post("/onboard", data={"teams": ["Cresskill-B13A-Park"]})
    assert _subs(uid) == before == {orphan_id: (OLD_TEAM, None),
                                    valid_id: ("Cresskill-B13A-Park", None)}


def test_onboard_search_for_a_different_team_archives_the_orphan(client):
    uid = _register(client, "a@example.com")
    orphan_id = _follow(uid, OLD_TEAM)
    other_orphan_id = _follow(uid, "Tenafly-G10C-Lopez")

    page = client.get(f"/onboard?replace={orphan_id}").text
    assert "BU12-Schwartzberg" in page
    assert f'name="replace" value="{orphan_id}"' in page
    assert 'value="Tenafly"' in page          # search prefilled with the old club

    # Submitting without picking anything new is not a decision about the orphan
    client.post("/onboard", data={"replace": str(orphan_id)})
    assert _subs(uid)[orphan_id] == (OLD_TEAM, None)

    client.post("/onboard", data={"teams": ["Cresskill-B13A-Park"], "replace": str(orphan_id)})
    subs = _subs(uid)
    assert subs.pop(orphan_id) == (OLD_TEAM, "previous")
    assert subs.pop(other_orphan_id) == ("Tenafly-G10C-Lopez", None)
    assert list(subs.values()) == [("Cresskill-B13A-Park", None)]


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def test_migration_upgrades_an_existing_database_and_is_idempotent(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config

    url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)   # alembic/env.py reads this
    cfg = Config(str(main.PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(main.PROJECT_ROOT / "alembic"))

    command.upgrade(cfg, "b3610d4bf24a")       # schema as deployed today
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO users (id, email) VALUES (1, 'a@example.com')"))
        conn.execute(sa.text(
            "INSERT INTO subscriptions (id, user_id, team_key, division, club, coach) "
            "VALUES (1, 1, 'Tenafly-B12B-Schwartzberg', 'B12B', 'Tenafly', 'Schwartzberg')"))

    command.upgrade(cfg, "head")
    insert = sa.text(
        "INSERT INTO subscriptions (user_id, team_key, division, club, coach, season) "
        "VALUES (1, 'Tenafly-B12B-Schwartzberg', 'B12B', 'Tenafly', 'Schwartzberg', :season)")
    with engine.begin() as conn:
        # Existing rows survive and are active
        assert conn.execute(sa.text("SELECT team_key, season FROM subscriptions")).all() == [
            ("Tenafly-B12B-Schwartzberg", None)]
        conn.execute(insert, {"season": "2026-spring"})      # archived copy: allowed
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        conn.execute(insert, {"season": None})               # second active copy: rejected

    # Re-running against a database that already has everything is a no-op
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM alembic_version"))
        conn.execute(sa.text("INSERT INTO alembic_version VALUES ('b3610d4bf24a')"))
    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM subscriptions")).scalar() == 2
    engine.dispose()


# ---------------------------------------------------------------------------
# merge_standings: seasons must not bleed into each other
# ---------------------------------------------------------------------------

def _game(number: str, date: str, gf: int = 1, ga: int = 0) -> dict:
    return {"game_number": number, "date": date, "goals_for": gf, "goals_against": ga,
            "opponent_club": "Nutley"}


def _team(team_raw: str, games: list[dict], **stats) -> dict:
    return {"team_raw": team_raw, "wins": 0, "losses": 0, "draws": 0, "points": 0,
            "games": games, **stats}


def _division(scraped_at: str, teams: list[dict], **extra) -> dict:
    return {"division": "B12A", "scraped_at": scraped_at, "teams": teams, **extra}


SPRING = _division("2026-07-19T07:56:13Z", [
    _team("Maroons-B12A-Breheny", [_game("407758", "2026-06-19")], wins=6, points=20),
    _team("Nutley-B12A-Clifford", [_game("407760", "2026-05-02")], wins=3, points=9),
])


def test_season_of():
    assert season_of("2026-07-31") == "2026-spring"
    assert season_of("2026-08-01") == "2026-fall"
    assert season_of("2026-12-20T10:00:00Z") == "2026-fall"
    assert season_of("2027-01-05") == "2027-spring"
    assert season_of("") is None and season_of(None) is None and season_of("TBD") is None


def test_merge_reused_division_code_drops_last_seasons_teams():
    fall = _division("2026-10-06T08:00:00Z", [
        _team("Tenafly-B12A-Kim", [_game("512001", "2026-09-13")], wins=1, points=3),
        _team("Cresskill-B12A-Park", []),
    ])
    merged, changes = merge_division(copy.deepcopy(SPRING), fall)

    assert [t["team_raw"] for t in merged["teams"]] == ["Tenafly-B12A-Kim", "Cresskill-B12A-Park"]
    assert [g["game_number"] for g in merged["teams"][0]["games"]] == ["512001"]
    assert merged["teams"][1]["games"] == []
    assert merged["scraped_at"] == fall["scraped_at"]
    # The drop is reported, so the run log shows it and the file gets rewritten
    assert any("Maroons-B12A-Breheny" in c and "REMOVED" in c for c in changes)


def test_merge_recurring_team_key_does_not_inherit_old_season_games():
    # Same key in both seasons; the new season has not kicked off yet.
    fall = _division("2026-09-01T08:00:00Z", [_team("Maroons-B12A-Breheny", [])])
    merged, _ = merge_division(copy.deepcopy(SPRING), fall)
    assert merged["teams"] == [_team("Maroons-B12A-Breheny", [])]

    # ...and once it has, only this season's games are there, even if a
    # stale file was re-committed with a fall timestamp in between.
    stale = {**copy.deepcopy(SPRING), "scraped_at": "2026-08-20T08:00:00Z"}
    fall = _division("2026-09-20T08:00:00Z", [
        _team("Maroons-B12A-Breheny", [_game("512010", "2026-09-13")])])
    merged, _ = merge_division(stale, fall)
    assert [g["game_number"] for g in merged["teams"][0]["games"]] == ["512010"]


def test_merge_explicit_season_field_wins_over_dates():
    # Site already reset for the fall while the calendar still says July.
    fall = _division("2026-07-28T08:00:00Z", [_team("Maroons-B12A-Breheny", [])],
                     season="2026-fall")
    merged, _ = merge_division(copy.deepcopy(SPRING), fall)
    assert merged["teams"][0]["games"] == []


def test_merge_within_a_season_still_unions_game_history():
    old = _division("2026-10-01T08:00:00Z", [
        _team("Tenafly-B12A-Kim", [_game("512001", "2026-09-13"), _game("512002", "2026-09-20", 0, 0)]),
    ])
    new = _division("2026-10-06T08:00:00Z", [
        _team("Tenafly-B12A-Kim", [_game("512002", "2026-09-20", 2, 1), _game("512003", "2026-10-04")],
              wins=2, points=6),
    ])
    merged, changes = merge_division(old, new)
    team = merged["teams"][0]
    # Old game the site no longer lists is preserved; fresh score wins on conflict
    assert [g["game_number"] for g in team["games"]] == ["512001", "512002", "512003"]
    assert (team["games"][1]["goals_for"], team["games"][1]["goals_against"]) == (2, 1)
    assert team["points"] == 6
    assert any("score changed" in c for c in changes)
    assert any("new game #512003" in c for c in changes)
