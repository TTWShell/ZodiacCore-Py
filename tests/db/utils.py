import os
from contextlib import contextmanager
from sqlmodel import SQLModel, Session, create_engine

# Default local development URLs
DEFAULT_PG_URL = "postgresql://postgres:@localhost:5432/zodiac_test"
DEFAULT_MYSQL_URL = "mysql+pymysql://root:root@localhost:3306/zodiac_test"

DB_URLS = [
    ("sqlite", "sqlite:///:memory:", None),
    (
        "postgresql",
        os.getenv("POSTGRES_URL", DEFAULT_PG_URL),
        {"options": "-c timezone=utc"},
    ),
    (
        "mysql",
        os.getenv("MYSQL_URL", DEFAULT_MYSQL_URL),
        {"init_command": "SET time_zone='+00:00'"},
    ),
]


@contextmanager
def managed_db_session(url, connect_args=None):
    """Manage the lifecycle of a database session."""
    extras = dict(connect_args=connect_args) if connect_args else {}
    engine = create_engine(url, **extras)

    try:
        SQLModel.metadata.drop_all(engine)
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            yield engine, session
    finally:
        engine.dispose()
