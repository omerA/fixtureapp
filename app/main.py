"""
app/main.py — FastAPI web app for TooInvolved standings tracker.

Routes:
  GET  /                  Landing page (redirects to /dashboard if logged in)
  GET  /register          Registration form
  POST /register          Create account -> /onboard
  GET  /login             Login form
  POST /login             Authenticate -> /dashboard
  POST /logout            Clear session -> /
  GET  /onboard           Team search + subscribe (protected)
  POST /onboard           Save subscriptions -> /dashboard
  POST /search            HTMX: return team result cards
  GET  /dashboard         Show subscribed teams (protected)
  GET  /team/{team_key}   Team detail: standings + results (protected)
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
from .db import get_db, init_db
from .models import Subscription, User
from .search import division_label, search_teams

PROJECT_ROOT = Path(__file__).parent.parent
STANDINGS_DIR = PROJECT_ROOT / "standings"

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
    m = re.match(r'^([BG])(\\d{2})', code)
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
    init_db()
    path = PROJECT_ROOT / "team_index.json"
    if path.exists():
        _team_index.update(json.loads(path.read_text()))
    yield


app = FastAPI(lifespan=lifespan, title="TooInvolved")
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


def _tr(request: Request, name: str, ctx: dict | None = None, **kwargs):
    context = ctx or {}
    context.update(kwargs)
    return templates.TemplateResponse(request, name, context)


def _build_card(sub: Subscription) -> dict:
    all_teams = _load_standings(sub.division)
    matched = next((t for t in all_teams if t["team_raw"] == sub.team_key), None)
    rank = next((i + 1 for i, t in enumerate(all_teams) if t["team_raw"] == sub.team_key), None)
    home_prefix = _detect_home_prefix(matched.get("games", [])) if matched else ""
    games = _annotate_games(matched.get("games", []), home_prefix) if matched else []
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
    return _tr(request, "team_detail.html", user=user, card=card)
