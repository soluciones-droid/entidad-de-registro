from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

# Configuration specific to the database dialect
is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {}

if is_sqlite:
    # Ensure directory exists for SQLite
    db_path_str = settings.database_url.replace("sqlite:///", "", 1)
    if not db_path_str.startswith(":memory:"):
        db_path = Path(db_path_str)
        db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # SQLite specific threading configuration
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from app import db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
