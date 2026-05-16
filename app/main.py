"""
app/main.py — FastAPI web app for FixtureApp standings tracker.

Routes:
  GET  /                              Landing page (redirects to /dashboard if logged in)
  GET  /register                      Registration form
  POST /register                      Create account -> /onboard
  GET  /login                         Login form
  POST /login                         Authenticate -> /dashboard
  POST /logout                        Clear session -> /
  GET  /onboard                       Team search + subscribe (protected)
  POST /onboard                       Save subscriptions -> /dashboard
  POST /search                        HTMX: return team result cards
  GET  /dashboard                     Show subscribed teams (protected)
  GET  /team/{team_key}               Team detail: standings + results (protected)
  GET  /team/{team_key}/matchup       Matchup preview vs. a division opponent (protected)
  GET  /settings                      Account settings + TeamSnap connection status
  GET  /auth/teamsnap                 Start TeamSnap OAuth flow (protected)
  GET  /auth/teamsnap/callback        TeamSnap OAuth callback
  POST /auth/teamsnap/disconnect      Remove TeamSnap connection
  GET  /teamsnap/connect              Link TeamSnap teams to NCSA subscriptions (protected)
  POST /teamsnap/link                 Save a TeamSnap → NCSA link
  POST /teamsnap/sync/{link_id}       Re-fetch roster for a link
  POST /teamsnap/unlink/{link_id}     Delete a link
"""
from __future__ import annotations

import json
import os
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from authlib.integrations.starlette_client import OAuth

from .auth import hash_password, verify_password
from .db import get_db
from .models import Subscription, TeamSnapLink, User
from .search import division_label, search_teams

PROJECT_ROOT = Path(__file__).parent.parent
STANDINGS_DIR = PROJECT_ROOT / "standings"
SCHEDULES_DIR = PROJECT_ROOT / "schedules"

_team_index: dict = {}

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
oauth.register(
    name="teamsnap",
    client_id=os.getenv("TEAMSNAP_CLIENT_ID"),
    client_secret=os.getenv("TEAMSNAP_CLIENT_SECRET"),
    authorize_url="https://auth.teamsnap.com/oauth/authorize",
    access_token_url="https://auth.teamsnap.com/oauth/token",
    client_kwargs={"scope": "read"},
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
templates.env.filters["fromjson"] = json.loads


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
    path = SCHEDULES_DIR / f"{division}.json"
    if not path.exists():
        return []
    games = json.loads(path.read_text()).get("games", [])
    upcoming = [
        g for g in games
        if g.get("is_upcoming")
        and (g.get("home_team") == team_raw or g.get("away_team") == team_raw)
    ]
    return sorted(upcoming, key=lambda g: (g.get("date", ""), g.get("time", "")))


def _tr(request: Request, name: str, ctx: dict | None = None, **kwargs):
    context = ctx or {}
    context.update(kwargs)
    return templates.TemplateResponse(request, name, context)


def _annotate_upcoming(games: list[dict], team_raw: str) -> list[dict]:
    """Add is_home, formatted date fields, and is_tbd flag to upcoming schedule games."""
    today = datetime.utcnow().date().isoformat()
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
    short = _division_short(sub.division)
    return {
        "sub": sub,
        "team_title": f"{short}-{sub.coach}",
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
    if not user.subscriptions:
        return RedirectResponse("/onboard", status_code=302)
    return RedirectResponse("/dashboard", status_code=302)


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------

@app.get("/onboard")
async def onboard_get(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    existing = [
        {"team_key": s.team_key, "division_label": division_label(s.division),
         "club": s.club, "coach": s.coach}
        for s in user.subscriptions
    ]
    return _tr(request, "onboard.html", user=user,
               existing_teams=existing, existing_count=len(existing))


@app.post("/onboard")
async def onboard_post(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    form = await request.form()
    team_keys = form.getlist("teams")

    if not team_keys:
        existing = [
            {"team_key": s.team_key, "division_label": division_label(s.division),
             "club": s.club, "coach": s.coach}
            for s in user.subscriptions
        ]
        return _tr(request, "onboard.html", user=user,
                   existing_teams=existing, existing_count=len(existing),
                   error="Select at least one team to continue.")

    db.query(Subscription).filter(Subscription.user_id == user.id).delete()
    for key in team_keys:
        info = _team_index.get("by_team", {}).get(key)
        if not info:
            continue
        db.add(Subscription(
            user_id=user.id,
            team_key=key,
            division=info["division"],
            club=info["club"],
            coach=info["coach"],
        ))
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
    if not user.subscriptions:
        return RedirectResponse("/onboard", status_code=302)

    cards = [
        _build_card(sub)
        for sub in sorted(user.subscriptions, key=lambda s: s.division)
    ]
    return _tr(request, "dashboard.html", user=user, cards=cards)


# ---------------------------------------------------------------------------
# Team detail
# ---------------------------------------------------------------------------

@app.get("/team/{team_key}")
async def team_detail(team_key: str, request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    sub = next(
        (s for s in user.subscriptions if s.team_key == team_key),
        None,
    )
    if not sub:
        return RedirectResponse("/dashboard", status_code=302)

    card = _build_card(sub)
    today = datetime.utcnow().date().isoformat()

    # Find a TeamSnap link for this subscription (if any)
    ts_link = db.query(TeamSnapLink).filter(
        TeamSnapLink.user_id == user.id,
        TeamSnapLink.ncsa_subscription_id == sub.id,
    ).first()
    roster: list[dict] = []
    if ts_link and ts_link.roster_json:
        import json as _json
        try:
            roster = _json.loads(ts_link.roster_json)
        except Exception:
            roster = []

    return _tr(request, "team_detail.html", user=user, card=card, today=today,
               ts_link=ts_link, roster=roster)


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

    sub = next((s for s in user.subscriptions if s.team_key == team_key), None)
    if not sub:
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


# ---------------------------------------------------------------------------
# Account settings
# ---------------------------------------------------------------------------

@app.get("/settings")
async def settings_get(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    links = db.query(TeamSnapLink).filter(TeamSnapLink.user_id == user.id).all()
    return _tr(request, "settings.html", user=user, links=links)


# ---------------------------------------------------------------------------
# TeamSnap OAuth
# ---------------------------------------------------------------------------

@app.get("/auth/teamsnap")
async def auth_teamsnap(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    redirect_uri = request.url_for("auth_teamsnap_callback")
    return await oauth.teamsnap.authorize_redirect(request, redirect_uri)


@app.get("/auth/teamsnap/callback", name="auth_teamsnap_callback")
async def auth_teamsnap_callback(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    try:
        token = await oauth.teamsnap.authorize_access_token(request)
    except Exception:
        return RedirectResponse("/settings?error=teamsnap", status_code=302)

    access_token = token.get("access_token")
    refresh_token = token.get("refresh_token")

    # Fetch the user's TeamSnap identity to get their numeric ID
    from teamsnap_client import TeamSnapClient, TeamSnapError
    try:
        client = TeamSnapClient(access_token)
        # /me returns the authenticated user's member record
        me_data = client._get("/me")
        me_items = client._items(me_data)
        ts_id = str(me_items[0].get("id", "")) if me_items else None
    except (TeamSnapError, Exception):
        ts_id = None

    user.teamsnap_id = ts_id
    user.teamsnap_access_token = access_token
    user.teamsnap_refresh_token = refresh_token
    db.commit()
    return RedirectResponse("/teamsnap/connect", status_code=302)


@app.post("/auth/teamsnap/disconnect")
async def auth_teamsnap_disconnect(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    user.teamsnap_id = None
    user.teamsnap_access_token = None
    user.teamsnap_refresh_token = None
    # Remove all links for this user
    db.query(TeamSnapLink).filter(TeamSnapLink.user_id == user.id).delete()
    db.commit()
    return RedirectResponse("/settings", status_code=302)


# ---------------------------------------------------------------------------
# TeamSnap connect / roster
# ---------------------------------------------------------------------------

def _fuzzy_match_subscription(ts_name: str, subscriptions: list) -> int | None:
    """
    Try to match a TeamSnap team name against NCSA subscriptions.
    Returns subscription.id of the best match, or None.
    """
    ts_lower = ts_name.lower()
    best_id = None
    best_score = 0
    for sub in subscriptions:
        candidate = f"{sub.club} {sub.coach}".lower()
        # Score = number of shared words
        ts_words = set(ts_lower.split())
        cand_words = set(candidate.split())
        score = len(ts_words & cand_words)
        if score > best_score:
            best_score = score
            best_id = sub.id
    return best_id if best_score > 0 else None


@app.get("/teamsnap/connect")
async def teamsnap_connect_get(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if not user.teamsnap_access_token:
        return RedirectResponse("/settings", status_code=302)

    from teamsnap_client import TeamSnapClient, TeamSnapError
    ts_teams = []
    error = None
    try:
        client = TeamSnapClient(user.teamsnap_access_token)
        ts_teams = client.get_teams()
    except TeamSnapError as e:
        if e.status_code == 401:
            error = "expired"
        else:
            error = "api"
    except Exception:
        error = "api"

    existing_links = {lnk.teamsnap_team_id: lnk for lnk in user.teamsnap_links}

    # Annotate each TeamSnap team with suggested match + existing link
    annotated = []
    for t in ts_teams:
        ts_id = str(t.get("id", ""))
        link = existing_links.get(ts_id)
        suggested_sub_id = (
            link.ncsa_subscription_id
            if link
            else _fuzzy_match_subscription(t.get("name", ""), user.subscriptions)
        )
        annotated.append({
            "ts_id": ts_id,
            "ts_name": t.get("name", ""),
            "link": link,
            "suggested_sub_id": suggested_sub_id,
        })

    return _tr(request, "teamsnap_connect.html",
               user=user,
               ts_teams=annotated,
               subscriptions=user.subscriptions,
               error=error)


@app.post("/teamsnap/link")
async def teamsnap_link_post(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    form = await request.form()
    ts_id = form.get("ts_id", "").strip()
    ts_name = form.get("ts_name", "").strip()
    sub_id_str = form.get("sub_id", "").strip()
    sub_id = int(sub_id_str) if sub_id_str.isdigit() else None

    if not ts_id:
        return RedirectResponse("/teamsnap/connect", status_code=302)

    # Validate subscription belongs to user
    if sub_id:
        sub = next((s for s in user.subscriptions if s.id == sub_id), None)
        if not sub:
            sub_id = None

    # Upsert the link
    link = db.query(TeamSnapLink).filter(
        TeamSnapLink.user_id == user.id,
        TeamSnapLink.teamsnap_team_id == ts_id,
    ).first()
    if link:
        link.ncsa_subscription_id = sub_id
        link.teamsnap_team_name = ts_name
    else:
        link = TeamSnapLink(
            user_id=user.id,
            teamsnap_team_id=ts_id,
            teamsnap_team_name=ts_name,
            ncsa_subscription_id=sub_id,
        )
        db.add(link)
    db.commit()
    db.refresh(link)

    # Immediately fetch roster
    if user.teamsnap_access_token:
        from teamsnap_client import TeamSnapClient, TeamSnapError
        import json as _json
        try:
            client = TeamSnapClient(user.teamsnap_access_token)
            members = client.get_members(ts_id)
            roster = [{"name": m.get("name", "")} for m in members if m.get("name")]
            link.roster_json = _json.dumps(roster)
            link.roster_synced_at = datetime.utcnow()
            db.commit()
        except (TeamSnapError, Exception):
            pass

    return RedirectResponse("/teamsnap/connect", status_code=302)


@app.post("/teamsnap/sync/{link_id}")
async def teamsnap_sync(link_id: int, request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    link = db.get(TeamSnapLink, link_id)
    if not link or link.user_id != user.id:
        return RedirectResponse("/teamsnap/connect", status_code=302)

    if user.teamsnap_access_token:
        from teamsnap_client import TeamSnapClient, TeamSnapError
        import json as _json
        try:
            client = TeamSnapClient(user.teamsnap_access_token)
            members = client.get_members(link.teamsnap_team_id)
            roster = [{"name": m.get("name", "")} for m in members if m.get("name")]
            link.roster_json = _json.dumps(roster)
            link.roster_synced_at = datetime.utcnow()
            db.commit()
        except TeamSnapError as e:
            if e.status_code == 401:
                return RedirectResponse("/teamsnap/connect?error=expired", status_code=302)

    # Redirect back to the team detail roster tab if linked, otherwise connect page
    if link.subscription:
        return RedirectResponse(
            f"/team/{link.subscription.team_key}?tab=roster",
            status_code=302,
        )
    return RedirectResponse("/teamsnap/connect", status_code=302)


@app.post("/teamsnap/unlink/{link_id}")
async def teamsnap_unlink(link_id: int, request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    link = db.get(TeamSnapLink, link_id)
    if link and link.user_id == user.id:
        db.delete(link)
        db.commit()
    return RedirectResponse("/teamsnap/connect", status_code=302)
