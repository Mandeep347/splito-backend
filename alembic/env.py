from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# ── Import all models so Alembic can detect them ─────────────────────────────
from app.db.session import Base
import app.domain.user.models       # noqa: F401
import app.domain.group.models      # noqa: F401
import app.domain.expense.models    # noqa: F401
import app.domain.settlement.models # noqa: F401
import app.domain.balance.models    # noqa: F401

from app.core.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Use sync URL for Alembic CLI (asyncpg doesn't work with Alembic's sync runner)
# Falls back to DATABASE_URL with driver swapped if SYNC_DATABASE_URL not set
def get_sync_url() -> str:
    if hasattr(settings, "sync_database_url") and settings.sync_database_url:
        return settings.sync_database_url
    # Auto-convert asyncpg URL to psycopg2
    return settings.database_url.replace(
        "postgresql+asyncpg://", "postgresql://"
    )


def run_migrations_offline() -> None:
    url = get_sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        get_sync_url(),
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
