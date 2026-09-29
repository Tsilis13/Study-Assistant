import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# A file called app.db in the folder you run the program from (created automatically).
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# check_same_thread=False: FastAPI uses several threads and SQLite must be told that is OK.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


# SQLite ignores foreign keys unless asked. This asks on every new connection.
@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Every model (table) inherits from this class."""


def get_db():
    """Yields a database session for one request and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
