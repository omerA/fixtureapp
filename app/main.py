"""
app/main.py — FastAPI web app for FixtureApp standings tracker.

Routes:
  GET  /                         Landing page (redirects to /dashboard if logged in)
  GET  /register                 Registration form
  POST /register                 Create account -> /onboard
  GET  /login                    Login form
  POST /login                    Authenticate -> /dashboard
  POST /logout                   Clear session -> /
  GET  /onboard                  Team search + subscribe (protected)
  POST /onboard                  Save subscriptions -> /dashboard
  POST /search                   HTMX: return team result cards
  GET  /dashboard                Show subscribed teams (protected)
  GET  /team/{team_key}          Team detail: standings + results (protected)
  GET  /team/{team_key}/matchup  Matchup preview vs. a division opponent (protected)
  POST /subscriptions/{id}/replace   New season: swap an orphaned team for a current one (protected)
  POST /subscriptions/{id}/unfollow  Stop following a team (protected)
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from authlib.integrations.starlette_client import OAuth

from .auth import hash_password, verify_password
from .db import get_db
from .models import Subscription, User
from .search import division_label, division_short, search_teams

PROJECT_ROOT = Path(__file__).parent.parent
STANDINGS_DIR = PROJECT_ROOT / "standings"
SCHEDULES_DIR = PROJECT_ROOT / "schedules"

# Parents are told to arrive this long before kickoff
WARMUP_MINUTES = 30

try:
    LEAGUE_TZ = ZoneInfo("America/New_York")
except ZoneInfoNotFoundError:  # no tz database on this machine
    LEAGUE_TZ = timezone.utc

_team_index: dict = {}

# How many same-club teams to offer when a followed team is gone in a new season
_MAX_SUGGESTIONS = 5

# Palette for crest colors (cycled by club name hash)
_CREST_PALETTE = [
    "#2EA76A", "#2B6FD9", "#7C1E2D", "#E9A13B",
    "#6B4FE8", "#0F4C8A", "#1B7A3E", "#C44D2F",
]


# ---------------------------------------------------------------------------
# Template helpers / Jinja2 globals + filters
# ---------------------------------------------------------------------------

def _crest_initials(name: str) -> str:
    words = name.split()
    letters = [w[0].upper() for w in words if w and w[0].isalpha()]
    return "".join(letters[:2]) or "?"


def _crest_color(name: str) -> str:
    return _CREST_PALETTE[abs(hash(name)) % len(_CREST_PALETTE)]


def _venue_label(code: str) -> str:
    """Convert venue code like 'TEN-Municipal' to 'Municipal'."""
    parts = code.split("-")
    meaningful = [p for p in parts if not (len(p) <= 5 and p.replace(" ", "").upper() == p.replace(" ", ""))]
    return " ".join(meaningful) if meaningful else code.replace("-", " ")


def _division_short(code: str) -> str:
    """'B09EW' -> 'BU9', 'G12A' -> 'GU12'"""
    import re
    m = re.match(r'^([BG])(\d{2})', code)
    if not m:
        return code
    gender, age = m.group(1), int(m.group(2))
    return f"{gender}U{age}"


def _detect_home_prefix(games: list[dict]) -> str:
    if not games:
        return ""
    prefixes = Counter(g["venue_code"].split("-")[0] for g in games)
    return prefixes.most_common(1)[0][0]


def _annotate_games(games: list[dict], home_prefix: str) -> list[dict]:
    result = []
    for g in games:
        try:
            d = datetime.strptime(g["date"], "%Y-%m-%d")
            month_year = d.strftime("%B %Y")
            weekday = d.strftime("%a").upper()
            day_num = d.day
        except ValueError:
            month_year, weekday, day_num = "Unknown", "?", "?"
        prefix = g["venue_code"].split("-")[0]
        result.append({
            **g,
            "is_home": prefix == home_prefix,
            "month_year": month_year,
            "weekday": weekday,
            "day_num": day_num,
            "venue_label": _venue_label(g["venue_code"]),
        })
    return result


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run any pending Alembic migrations on startup.
    # On Railway this is belt-and-suspenders (railway.toml already runs
    # `alembic upgrade head` before the process starts), but it guarantees
    # correctness in local dev and other environments too.
    from alembic.config import Config as AlembicConfig
    from alembic import command as alembic_command
    alembic_cfg = AlembicConfig(str(PROJECT_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    alembic_command.upgrade(alembic_cfg, "head")

    path = PROJECT_ROOT / "team_index.json"
    if path.exists():
        _team_index.update(json.loads(path.read_text()))
    yield


app = FastAPI(lifespan=lifespan, title="FixtureApp")
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret-change-in-production"),
)
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals["crest_initials"] = _crest_initials
templates.env.globals["crest_color"] = _crest_color
templates.env.filters["venue_label"] = _venue_label


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_user(request: Request, db: Session) -> User | None:
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.get(User, uid)


def _load_standings(division: str) -> list[dict]:
    path = STANDINGS_DIR / f"{division}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("teams", [])


# ---------------------------------------------------------------------------
# Season rollover helpers
# ---------------------------------------------------------------------------

def _active_subs(user: User) -> list[Subscription]:
    """Subscriptions for the current season (archived rows carry a season label)."""
    return [s for s in user.subscriptions if s.season is None]


def _is_orphaned(sub: Subscription) -> bool:
    """
    True when an active subscription's team is no longer in the index (new
    season). If the index failed to load or is empty nothing is orphaned, so
    a bad deploy cannot make every user's teams vanish.
    """
    by_team = _team_index.get("by_team")
    if not by_team:
        return False
    return sub.season is None and sub.team_key not in by_team


def _previous_season() -> str:
    """Label for archived rows: the season before the index's ('2026-fall' -> '2026-spring')."""
    m = re.match(r"^(\d{4})-(spring|fall)$", str(_team_index.get("season", "")))
    if not m:
        return "previous"
    year = int(m.group(1))
    return f"{year}-spring" if m.group(2) == "fall" else f"{year - 1}-fall"


def _division_gender_age(code: str) -> tuple[str, int] | None:
    """'B12A' -> ('B', 12), 'G08C7' -> ('G', 8)"""
    m = re.match(r"^([BG])(\d{2})", code)
    return (m.group(1), int(m.group(2))) if m else None


def _suggest_teams(sub: Subscription, exclude: set[str]) -> list[dict]:
    """
    This season's teams from the orphaned subscription's club, likeliest
    first: same gender, then age group closest to where the kids are now,
    then same coach surname.
    """
    by_team = _team_index.get("by_team", {})
    old = _division_gender_age(sub.division)
    # Age groups move up a year in the fall; a spring season keeps the fall's.
    step = 0 if str(_team_index.get("season", "")).endswith("-spring") else 1
    ranked = []
    for key in _team_index.get("by_club", {}).get(sub.club, []):
        info = by_team.get(key)
        if not info or key in exclude:
            continue
        new = _division_gender_age(info["division"])
        comparable = old is not None and new is not None
        same_coach = info["coach"].strip().lower() == sub.coach.strip().lower()
        ranked.append((
            (
                0 if comparable and new[0] == old[0] else 1,
                abs(new[1] - (old[1] + step)) if comparable else 99,
                0 if same_coach else 1,
                info["division"],
                key,
            ),
            {
                "team_key": key,
                "club": info["club"],
                "coach": info["coach"],
                "division_label": division_label(info["division"]),
                "division_short": division_short(info["division"]),
                "same_coach": same_coach,
            },
        ))
    ranked.sort(key=lambda r: r[0])
    return [team for _, team in ranked[:_MAX_SUGGESTIONS]]


def _orphan_label(sub: Subscription) -> dict:
    """What an orphaned subscription was, in the dashboard card's title/subtitle format."""
    return {
        "sub": sub,
        "team_title": f"{_division_short(sub.division)}-{sub.coach}",
        "team_subtitle": sub.club,
        "division_label": division_label(sub.division),
    }


def _own_orphan(user: User, raw_id) -> Subscription | None:
    """The user's orphaned subscription with this id, or None."""
    try:
        sub_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    return next(
        (s for s in user.subscriptions if s.id == sub_id and _is_orphaned(s)),
        None,
    )


def _archive(db: Session, sub: Subscription) -> None:
    """
    Retire an orphaned subscription without losing it: the row stays, tagged
    with the season it belonged to, so historic teams can be shown later.
    """
    label = _previous_season()
    duplicate = db.query(Subscription).filter(
        Subscription.user_id == sub.user_id,
        Subscription.team_key == sub.team_key,
        Subscription.season == label,
        Subscription.id != sub.id,
    ).first()
    if duplicate:
        # Already on record for that season; a second copy adds nothing.
        db.delete(sub)
    else:
        sub.season = label


# ---------------------------------------------------------------------------
# Matchup helpers
# ---------------------------------------------------------------------------

def _form_points(form: str) -> int:
    """W=3, D=1, L=0 across the form string."""
    return sum(3 if r == 'W' else 1 if r == 'D' else 0 for r in form)


def _sorted_standings(teams: list[dict]) -> list[dict]:
    """Sort by points → goal difference → goals for (NCSA tiebreaker order)."""
    return sorted(teams, key=lambda t: (
        -t.get('points', 0),
        -(t.get('goals_for', 0) - t.get('goals_against', 0)),
        -t.get('goals_for', 0),
    ))


def _result_against(team: dict, opponent_club: str) -> dict | None:
    """Most recent meeting of team vs opponent_club. None if not played."""
    matches = [
        g for g in team.get('games', [])
        if g.get('opponent_club', '').strip() == opponent_club.strip()
    ]
    if not matches:
        return None
    matches.sort(key=lambda g: g.get('date', ''), reverse=True)
    m = matches[0]
    return {
        'result': m['result'],
        'goals_for': m['goals_for'],
        'goals_against': m['goals_against'],
        'count': len(matches),
    }


def _common_opponents_rows(my_team: dict, opp_team: dict, all_teams: list[dict]) -> list[dict]:
    """
    Returns one row per club both teams have played, sorted by that club's
    current standings position (strongest first).
    """
    clubs_a = {g.get('opponent_club', '').strip() for g in my_team.get('games', []) if g.get('opponent_club')}
    clubs_b = {g.get('opponent_club', '').strip() for g in opp_team.get('games', []) if g.get('opponent_club')}
    common = clubs_a & clubs_b

    ranked = _sorted_standings(all_teams)
    rank_by_club = {t['club'].strip(): i + 1 for i, t in enumerate(ranked)}

    rows = []
    for club in common:
        rows.append({
            'club': club,
            'standings_pos': rank_by_club.get(club, 999),
            'result_a': _result_against(my_team, club),
            'result_b': _result_against(opp_team, club),
        })
    rows.sort(key=lambda r: r['standings_pos'])
    return rows


def _load_upcoming_games(division: str, team_raw: str) -> list[dict]:
    """Return upcoming games for a specific team from the schedule JSON, sorted by date."""
    games = _schedule_games(division)
    listed_as = _schedule_name(games, division, team_raw)
    upcoming = [
        # Hand the game back under the name the caller knows the team by
        {**g, **{side: team_raw for side in ("home_team", "away_team") if g.get(side) == listed_as}}
        for g in games
        if g.get("is_upcoming")
        and (g.get("home_team") == listed_as or g.get("away_team") == listed_as)
    ]
    return sorted(upcoming, key=lambda g: (g.get("date", ""), g.get("time", "")))


def _schedule_games(division: str) -> list[dict]:
    path = SCHEDULES_DIR / f"{division}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("games", [])


def _team_title(division: str, team_raw: str) -> str:
    """'BU12-Leuer' from a 'Club-Division-Coach' team name."""
    return f"{_division_short(division)}-{team_raw.split('-')[-1]}"


def _rename(sub: Subscription) -> dict | None:
    """
    If the league has started listing a followed team under a new name,
    describe the change (the page shows the new name, and announces it once).
    """
    listed_as = _schedule_name(_schedule_games(sub.division), sub.division, sub.team_key)
    if listed_as == sub.team_key:
        return None
    return {
        "id": f"{sub.team_key}>{listed_as}",
        "old_title": _team_title(sub.division, sub.team_key),
        "new_title": _team_title(sub.division, listed_as),
        "club": sub.club,
        "initials": _crest_initials(sub.club),
        "color": _crest_color(sub.club),
    }


def _renames(subs: list[Subscription]) -> list[dict]:
    return [r for r in map(_rename, subs) if r]


def _schedule_name(games: list[dict], division: str, team_raw: str) -> str:
    """
    The name the schedule lists a team under. The league sometimes renames a
    team (usually a new coach) on its schedule page before its standings page,
    so a team from the standings can be missing from its own schedule. If the
    schedule has exactly one team from the same club that the standings don't
    know, that is the same team; anything less certain is left unmatched.
    """
    scheduled = {g.get(side) for g in games for side in ("home_team", "away_team")}
    if team_raw in scheduled:
        return team_raw
    in_standings = {t["team_raw"] for t in _load_standings(division)}
    if team_raw not in in_standings:
        return team_raw
    club = team_raw.split("-")[0]
    renamed = [
        name for name in scheduled
        if name and name not in in_standings and name.split("-")[0] == club
    ]
    return renamed[0] if len(renamed) == 1 else team_raw


def _today():
    """Today's date where the league plays (a UTC date rolls over mid-evening there)."""
    return datetime.now(LEAGUE_TZ).date()


def _clock(time_str: str) -> datetime | None:
    """Parse the site's '04:15 PM' into a datetime (date part is meaningless)."""
    try:
        return datetime.strptime(time_str.strip(), "%I:%M %p")
    except (ValueError, AttributeError):
        return None


def _show_time(t: datetime) -> str:
    return t.strftime("%I:%M %p").lstrip("0")


def _load_fields(division: str) -> dict:
    """field_id -> field info for a division; {} for schedule files scraped before fields were kept."""
    path = SCHEDULES_DIR / f"{division}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text()).get("fields", {})


def _maps_url(address: str) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(address)


def _upcoming_for(subs: list[Subscription]) -> tuple[list[dict], list[dict]]:
    """
    Every upcoming game across the given subscriptions, as
    (days, tbd): days is a list of {"date", "label", "badge", "games"} in
    calendar order with games in kickoff order; tbd holds postponed games.
    """
    today = _today()
    by_date: dict[str, list[dict]] = {}
    tbd: list[dict] = []
    seen: dict[tuple[str, str], dict] = {}

    for sub in subs:
        fields = _load_fields(sub.division)
        renamed = _rename(sub)
        title = renamed["new_title"] if renamed else _team_title(sub.division, sub.team_key)
        for g in _annotate_upcoming(_load_upcoming_games(sub.division, sub.team_key), sub.team_key):
            key = (g.get("division", sub.division), g.get("game_id", ""))
            if key in seen:
                # The parent follows both sides of this game: one row, both teams
                seen[key]["also_following"] = title
                continue
            kickoff = _clock(g.get("time", ""))
            place = fields.get(g.get("field_id", ""), {})
            game = {
                **g,
                "sub": sub,
                "team_title": title,
                "team_subtitle": sub.club,
                "kickoff": _show_time(kickoff) if kickoff else g.get("time", ""),
                "arrive_by": _show_time(kickoff - timedelta(minutes=WARMUP_MINUTES)) if kickoff else "",
                "sort_minutes": kickoff.hour * 60 + kickoff.minute if kickoff else 24 * 60,
                "address": place.get("address", ""),
                "maps_url": _maps_url(place["address"]) if place.get("address") else "",
                "field_details": place.get("details", ""),
                "field_comments": place.get("comments", ""),
            }
            seen[key] = game
            if g["is_tbd"]:
                tbd.append(game)
            else:
                by_date.setdefault(g["date"], []).append(game)

    days = []
    for date_str in sorted(by_date):
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        gap = (d - today).days
        days.append({
            "date": date_str,
            "label": f"{d.strftime('%A, %B')} {d.day}",
            "badge": "Today" if gap == 0 else "Tomorrow" if gap == 1 else "",
            "games": sorted(by_date[date_str], key=lambda x: (x["sort_minutes"], x["team_title"])),
        })
    tbd.sort(key=lambda x: (x["team_title"], x.get("opponent_club", "")))
    return days, tbd


def _tr(request: Request, name: str, ctx: dict | None = None, **kwargs):
    context = ctx or {}
    context.update(kwargs)
    return templates.TemplateResponse(request, name, context)


def _annotate_upcoming(games: list[dict], team_raw: str) -> list[dict]:
    """Add is_home, formatted date fields, and is_tbd flag to upcoming schedule games."""
    today = _today().isoformat()
    result = []
    for g in games:
        try:
            d = datetime.strptime(g["date"], "%Y-%m-%d")
            month_year = d.strftime("%B %Y")
            weekday = d.strftime("%a").upper()
            day_num = d.day
        except ValueError:
            month_year, weekday, day_num = "Unknown", "?", "?"
        opponent = g["away_team"] if g["home_team"] == team_raw else g["home_team"]
        opponent_club = opponent.split("-")[0] if opponent else ""
        field = g.get("field", "")
        # Postponed/rescheduled: date is past OR field explicitly says "To Be Scheduled"
        is_tbd = g.get("date", "") < today or "to be scheduled" in field.lower()
        result.append({
            **g,
            "is_home": g["home_team"] == team_raw,
            "opponent_raw": opponent,
            "opponent_club": opponent_club,
            "month_year": month_year,
            "weekday": weekday,
            "day_num": day_num,
            "is_tbd": is_tbd,
        })
    # Confirmed games first (by date/time), TBD games at the bottom
    result.sort(key=lambda x: (x["is_tbd"], x.get("date", ""), x.get("time", "")))
    return result


def _build_card(sub: Subscription) -> dict:
    all_teams = _load_standings(sub.division)
    matched = next((t for t in all_teams if t["team_raw"] == sub.team_key), None)
    rank = next((i + 1 for i, t in enumerate(all_teams) if t["team_raw"] == sub.team_key), None)
    home_prefix = _detect_home_prefix(matched.get("games", [])) if matched else ""
    games = _annotate_games(matched.get("games", []), home_prefix) if matched else []
    upcoming_raw = _load_upcoming_games(sub.division, sub.team_key)
    upcoming = _annotate_upcoming(upcoming_raw, sub.team_key)
    # next_confirmed: first non-TBD game, used for dashboard preview + matchday banner
    next_confirmed = next((g for g in upcoming if not g["is_tbd"]), None)
    renamed = _rename(sub)
    return {
        "sub": sub,
        "team_title": renamed["new_title"] if renamed else _team_title(sub.division, sub.team_key),
        "renamed": renamed,
        "team_subtitle": sub.club,
        "division_label": division_label(sub.division),
        "team": matched,
        "standings": all_teams,
        "rank": rank,
        "total_teams": len(all_teams),
        "games": list(reversed(games)),  # newest first
        "upcoming": upcoming,
        "next_confirmed": next_confirmed,
    }


# ---------------------------------------------------------------------------
# Landing
# ---------------------------------------------------------------------------

@app.get("/")
async def index(request: Request, db: Session = Depends(get_db)):
    if _session_user(request, db):
        return RedirectResponse("/dashboard", status_code=302)
    return _tr(request, "index.html", user=None)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.get("/register")
async def register_get(request: Request, db: Session = Depends(get_db)):
    if _session_user(request, db):
        return RedirectResponse("/dashboard", status_code=302)
    return _tr(request, "register.html", user=None)


@app.post("/register")
async def register_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        return _tr(request, "register.html", user=None,
                   error="An account with that email already exists.", email=email)
    if len(password) < 8:
        return _tr(request, "register.html", user=None,
                   error="Password must be at least 8 characters.", email=email)
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    return RedirectResponse("/onboard", status_code=302)


@app.get("/login")
async def login_get(request: Request, db: Session = Depends(get_db)):
    if _session_user(request, db):
        return RedirectResponse("/dashboard", status_code=302)
    return _tr(request, "login.html", user=None)


@app.post("/login")
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return _tr(request, "login.html", user=None,
                   error="Invalid email or password.", email=email)
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=302)


@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

@app.get("/auth/google")
async def auth_google(request: Request):
    redirect_uri = request.url_for("auth_google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback")
async def auth_google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo")
    if not user_info:
        return RedirectResponse("/login?error=google", status_code=302)

    google_id = user_info["sub"]
    email = user_info["email"]

    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_id = google_id
        else:
            user = User(email=email, google_id=google_id)
            db.add(user)
        db.commit()
        db.refresh(user)

    request.session["user_id"] = user.id
    if not _active_subs(user):
        return RedirectResponse("/onboard", status_code=302)
    return RedirectResponse("/dashboard", status_code=302)


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------

def _onboard_page(request: Request, user: User, replace=None, error: str | None = None):
    """
    Render the team picker. Only this season's followed teams are preselected:
    orphaned ones are handled on the dashboard and are never part of the form,
    so submitting it cannot drop them by accident. `replace` is the id of an
    orphaned subscription the user is searching for a replacement for.
    """
    existing = [
        {"team_key": s.team_key, "division_label": division_label(s.division),
         "club": s.club, "coach": s.coach}
        for s in _active_subs(user) if not _is_orphaned(s)
    ]
    replacing = _own_orphan(user, replace)
    return _tr(request, "onboard.html", user=user,
               existing_teams=existing, existing_count=len(existing),
               replacing=_orphan_label(replacing) if replacing else None,
               initial_query=replacing.club if replacing else "",
               error=error)


@app.get("/onboard")
async def onboard_get(request: Request, replace: str = "", db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return _onboard_page(request, user, replace=replace)


@app.post("/onboard")
async def onboard_post(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    form = await request.form()
    by_team = _team_index.get("by_team", {})
    replace = form.get("replace")
    # Keep only teams that exist this season, de-duplicated in submitted order
    team_keys = [k for k in dict.fromkeys(form.getlist("teams")) if k in by_team]

    if not team_keys:
        return _onboard_page(request, user, replace=replace,
                             error="Select at least one team to continue.")

    # The form lists this season's teams only, so sync just those rows.
    # Orphaned subscriptions (awaiting a re-pick) and archived ones are not
    # in the form and must survive it.
    current = {s.team_key: s for s in _active_subs(user) if not _is_orphaned(s)}
    replacing = _own_orphan(user, replace)
    for key, sub in current.items():
        if key not in team_keys:
            db.delete(sub)
    added = [key for key in team_keys if key not in current]
    for key in added:
        info = by_team[key]
        db.add(Subscription(
            user_id=user.id,
            team_key=key,
            division=info["division"],
            club=info["club"],
            coach=info["coach"],
        ))
    # Arrived via "search for a different team" and picked one: the orphan
    # has been dealt with, so retire it.
    if replacing and added:
        _archive(db, replacing)
    db.commit()
    return RedirectResponse("/dashboard", status_code=302)


# ---------------------------------------------------------------------------
# Search (HTMX endpoint)
# ---------------------------------------------------------------------------

@app.post("/search")
async def search(
    request: Request,
    q: str = Form(""),
    db: Session = Depends(get_db),
):
    if not _session_user(request, db):
        return HTMLResponse("", status_code=204)
    results = search_teams(q, _team_index, limit=15)
    return _tr(request, "partials/search_results.html", teams=results, query=q)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    active = sorted(_active_subs(user), key=lambda s: s.division)
    if not active:
        return RedirectResponse("/onboard", status_code=302)

    # New season: teams that are gone from the index are not rendered as
    # cards; the user is asked to pick again, with same-club suggestions.
    current = [s for s in active if not _is_orphaned(s)]
    following = {s.team_key for s in current}
    cards = [_build_card(sub) for sub in current]
    orphans = [
        {**_orphan_label(sub), "suggestions": _suggest_teams(sub, exclude=following)}
        for sub in active if _is_orphaned(sub)
    ]
    return _tr(request, "dashboard.html", user=user, cards=cards, orphans=orphans,
               renames=[c["renamed"] for c in cards if c["renamed"]])


# ---------------------------------------------------------------------------
# Upcoming games across all followed teams
# ---------------------------------------------------------------------------

@app.get("/upcoming")
async def upcoming(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    active = _active_subs(user)
    if not active:
        return RedirectResponse("/onboard", status_code=302)

    # Teams that are gone this season have no schedule; the dashboard handles them
    current = [s for s in active if not _is_orphaned(s)]
    days, tbd = _upcoming_for(current)
    return _tr(request, "upcoming.html", user=user, days=days, tbd=tbd,
               team_count=len(current), warmup_minutes=WARMUP_MINUTES,
               needs_repick=len(current) < len(active), renames=_renames(current))


# ---------------------------------------------------------------------------
# Season rollover: re-pick / stop following
# ---------------------------------------------------------------------------

def _own_active_sub(user: User, sub_id: int) -> Subscription:
    """The current user's active subscription with this id, else 404."""
    sub = next((s for s in _active_subs(user) if s.id == sub_id), None)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub


@app.post("/subscriptions/{sub_id}/replace")
async def subscription_replace(
    sub_id: int,
    request: Request,
    team_key: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    sub = _own_active_sub(user, sub_id)
    info = _team_index.get("by_team", {}).get(team_key)
    if not info:
        raise HTTPException(status_code=400, detail="Unknown team")
    # Only a team that is gone can be swapped (also makes a double-submit harmless)
    if not _is_orphaned(sub):
        return RedirectResponse("/dashboard", status_code=302)

    already_following = any(s.team_key == team_key for s in _active_subs(user))
    _archive(db, sub)
    if not already_following:
        db.add(Subscription(
            user_id=user.id,
            team_key=team_key,
            division=info["division"],
            club=info["club"],
            coach=info["coach"],
        ))
    db.commit()
    return RedirectResponse("/dashboard", status_code=302)


@app.post("/subscriptions/{sub_id}/unfollow")
async def subscription_unfollow(sub_id: int, request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    # The parent's explicit choice, so this is a real delete (not an archive)
    db.delete(_own_active_sub(user, sub_id))
    db.commit()
    return RedirectResponse("/dashboard", status_code=302)


# ---------------------------------------------------------------------------
# Team detail
# ---------------------------------------------------------------------------

@app.get("/team/{team_key}")
async def team_detail(team_key: str, request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    sub = next(
        (s for s in _active_subs(user) if s.team_key == team_key),
        None,
    )
    # Orphaned (gone this season): the dashboard handles the re-pick
    if not sub or _is_orphaned(sub):
        return RedirectResponse("/dashboard", status_code=302)

    card = _build_card(sub)
    today = _today().isoformat()
    return _tr(request, "team_detail.html", user=user, card=card, today=today,
               renames=[card["renamed"]] if card["renamed"] else [])


# ---------------------------------------------------------------------------
# Matchup preview
# ---------------------------------------------------------------------------

@app.get("/team/{team_key}/matchup")
async def matchup_preview(
    team_key: str,
    request: Request,
    opp: str = "",
    db: Session = Depends(get_db),
):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    sub = next((s for s in _active_subs(user) if s.team_key == team_key), None)
    if not sub or _is_orphaned(sub):
        return RedirectResponse("/dashboard", status_code=302)

    all_teams = _load_standings(sub.division)
    my_team = next((t for t in all_teams if t['team_raw'] == team_key), None)
    other_teams = [t for t in all_teams if t['team_raw'] != team_key]

    ranked = _sorted_standings(all_teams)
    rank_by_team = {t['team_raw']: i + 1 for i, t in enumerate(ranked)}
    my_rank = rank_by_team.get(team_key, '—')

    opp_team = None
    opp_rank = '—'
    common_rows: list[dict] = []
    summary_a: dict = {'W': 0, 'D': 0, 'L': 0}
    summary_b: dict = {'W': 0, 'D': 0, 'L': 0}
    form_pts_a = _form_points(my_team.get('form', '')) if my_team else 0
    form_pts_b = 0

    # Find the scheduled game between my team and the opponent (if data exists)
    raw_upcoming = _load_upcoming_games(sub.division, team_key)
    upcoming_annotated = _annotate_upcoming(raw_upcoming, team_key)
    matchup_game = None

    if opp:
        opp_team = next((t for t in all_teams if t['team_raw'] == opp), None)
        matchup_game = next(
            (g for g in upcoming_annotated if g.get('opponent_raw') == opp),
            None,
        )
        if opp_team and my_team:
            opp_rank = rank_by_team.get(opp, '—')
            common_rows = _common_opponents_rows(my_team, opp_team, all_teams)
            for row in common_rows:
                if row['result_a']:
                    summary_a[row['result_a']['result']] += 1
                if row['result_b']:
                    summary_b[row['result_b']['result']] += 1
            form_pts_b = _form_points(opp_team.get('form', ''))

    return _tr(request, "matchup.html",
        user=user,
        sub=sub,
        my_team=my_team,
        other_teams=other_teams,
        opp_team=opp_team,
        opp_key=opp,
        my_rank=my_rank,
        opp_rank=opp_rank,
        matchup_game=matchup_game,
        common_rows=common_rows,
        summary_a=summary_a,
        summary_b=summary_b,
        form_pts_a=form_pts_a,
        form_pts_b=form_pts_b,
        division_label=division_label(sub.division),
    )
