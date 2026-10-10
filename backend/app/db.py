from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_config(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")


Session = sessionmaker(engine, expire_on_commit=False)


def session():
    with Session() as db:
        yield db
