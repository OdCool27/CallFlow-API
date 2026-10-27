from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

if not settings.database_url.startswith("sqlite:"):
    raise ValueError("This runtime supports SQLite; sql/ contains separate SQL Server examples")

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False, "timeout": 15})


@event.listens_for(engine, "connect")
def sqlite_constraints(connection, _):
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=15000")


SessionLocal = sessionmaker(autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    with SessionLocal() as db:
        yield db
