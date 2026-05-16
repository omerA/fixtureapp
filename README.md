# FixtureApp

A parent-facing web app for following kids' teams in NCSA NJ youth soccer leagues. Shows standings, results, and form — across all the divisions your kids play in.

## What it does

- **Onboarding**: search for your kids' teams by club, coach, or division; subscribe to as many as you want
- **Dashboard**: see all followed teams at a glance — rank, W/D/L, points, last-5 form chips
- **Team detail**: full standings table (subscribed team highlighted), results grouped by month

Data is scraped from [ncsanj.com](https://www.ncsanj.com) — a volunteer-run league, so the scraper is deliberately polite (2s delay, 12h cache, identifying User-Agent).

## Stack

| Layer | Tech |
|---|---|
| Web app | FastAPI + Jinja2 templates |
| Interactivity | HTMX (search), vanilla JS (tabs) |
| Styling | Tailwind CSS CDN + CSS custom properties |
| Database | SQLite (local) / Postgres (Railway) via SQLAlchemy + Alembic |
| Auth | bcrypt session auth (Clerk migration planned) |
| Scraper | `requests` + `BeautifulSoup4` |

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # fill in SECRET_KEY and SCRAPER_CONTACT

# Apply database migrations (creates app.db on first run)
alembic upgrade head

# Build the team index (scrapes all 169 NCSA divisions — ~6 min first run)
python build_team_index.py -v

# Build standings for teams in the index
python build_standings.py

# Run the app
uvicorn app.main:app --reload
```

Then visit `http://localhost:8000`.

> **Note:** The app also runs `alembic upgrade head` automatically at startup, so
> skipping the manual step above is safe — it just means the first request after
> a fresh clone takes a fraction of a second longer.

### Database migrations workflow

When you change a model (`app/models.py`):

```bash
# 1. Generate a migration (compares models against current DB schema)
alembic revision --autogenerate -m "describe_what_changed"

# 2. Review the generated file in alembic/versions/
# 3. Apply it locally
alembic upgrade head

# 4. Commit both the model change and the migration file
git add app/models.py alembic/versions/
git commit -m "feat: ..."
```

Railway applies the migration automatically on the next deploy via
`alembic upgrade head` in the start command — no manual step needed in production.

To roll back one step locally:

```bash
alembic downgrade -1
```

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes (prod) | Session signing key. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SCRAPER_CONTACT` | Yes | Your email, embedded in the scraper's User-Agent so NCSA can reach you |
| `DATABASE_URL` | Prod only | Set automatically by Railway when you provision a Postgres plugin. Leave unset locally to use SQLite. |

### Scraper notes

- 2-second delay between requests
- 12-hour disk cache in `./cache/` — re-runs within that window are free
- Stops on any unexpected response

If NCSA ever asks you to stop scraping, stop. The configuration is well within polite limits but respect any direct request.

## Railway deployment

1. Create a new Railway project and connect the GitHub repo.
2. In the Railway dashboard, add a **Postgres** plugin to the project — Railway injects `DATABASE_URL` automatically.
3. Add the following environment variables under **Variables**:
   - `SECRET_KEY` — generate with `python -c "import secrets; print(secrets.token_hex(32))"`
   - `SCRAPER_CONTACT` — your email address
   - `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — from Google Cloud Console (OAuth 2.0)
4. Deploy. The start command in `railway.toml` runs `alembic upgrade head` before starting the server, so the Postgres schema is created/migrated on every deploy.

### First deploy on an existing Railway Postgres DB

If you are migrating from the old SQLite-based setup (where users were reset on every deploy), the Postgres DB starts empty. Users will need to re-register once — their subscriptions are not lost, they just need to re-enter their email/password or sign in with Google.

## Data files

`team_index.json` and `standings/*.json` are committed as a starting point. The GitHub Actions workflow (see below) refreshes them nightly and commits the updated files back.

## Repository layout

```
app/               FastAPI application
  main.py          Routes + Jinja2 helpers
  models.py        SQLAlchemy models (User, Subscription)
  auth.py          bcrypt password hashing
  search.py        Team search against team_index.json
  templates/       Jinja2 HTML templates
  static/          CSS
fetcher.py         HTTP client (rate-limited, cached)
parser.py          HTML → standings data
build_team_index.py  Scrape all divisions → team_index.json
build_standings.py   Scrape watched divisions → standings/*.json
standings/         Per-division standings JSON (generated)
team_index.json    Full team directory (generated)
```

## Roadmap

- [ ] **IDP (Clerk)** — replace bcrypt session auth with Clerk for social logins and better session management
- [ ] **GitHub Actions scraper** — nightly cron to refresh `team_index.json` and `standings/*.json`
- [ ] **Railway deploy** — `Procfile` / `railway.toml` for one-click deploy
- [ ] **Push notifications** — notify parents of upcoming games and new results
