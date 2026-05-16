import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Alembic config object ─────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── App metadata ──────────────────────────────────────────────────────────
# Import all models so SQLAlchemy registers them against Base.metadata
from app.db import Base  # noqa: E402
from app.models import Subscription, User  # noqa: E402, F401

target_metadata = Base.metadata


# ── URL resolution ────────────────────────────────────────────────────────
def _get_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        # Railway (and older Heroku) emit postgres:// which SQLAlchemy 1.4+ rejects
        return url.replace("postgres://", "postgresql://", 1)
    # Local fallback: SQLite next to the project root
    from pathlib import Path
    db_path = Path(__file__).parent.parent / "app.db"
    return f"sqlite:///{db_path}"


def run_migrations_offline() -> None:
    """Run without creating an engine — useful for generating SQL scripts."""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite doesn't support ALTER TABLE natively; use batch mode
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run against a live database connection."""
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _get_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # batch mode keeps SQLite ALTER TABLE working during local dev
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
