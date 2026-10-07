"""The Postgres driver must be named explicitly (SQLAlchemy 2.1 defaults to psycopg 3)."""
import pytest
from sqlalchemy.engine import make_url


@pytest.mark.parametrize("url", [
    "postgres://user:pw@host:5432/railway",
    "postgresql://user:pw@host:5432/railway",
])
def test_postgres_urls_use_installed_driver(url):
    # Imported here, not at module level: app.db builds its engine on import and
    # test_season_rollover.py must point it at a throwaway database first.
    from app.db import normalize_db_url

    normalized = normalize_db_url(url)
    assert normalized == "postgresql+psycopg2://user:pw@host:5432/railway"
    # Resolving the dialect imports the driver, which is what crashed the deploy
    assert make_url(normalized).get_dialect().driver == "psycopg2"
    make_url(normalized).get_dialect().import_dbapi()


@pytest.mark.parametrize("url", [
    "postgresql+psycopg2://user:pw@host/db",
    "sqlite:///app.db",
])
def test_other_urls_are_left_alone(url):
    from app.db import normalize_db_url

    assert normalize_db_url(url) == url
