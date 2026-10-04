from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from versionweaver.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def normalized_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://") and "+" not in url.split(":", 1)[0]:
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def build_engine(settings: Settings | None = None) -> Engine:
    config = settings or get_settings()
    url = normalized_database_url(config.database_url)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def init_database(target_engine: Engine | None = None) -> None:
    from versionweaver.persistence import models  # noqa: F401

    Base.metadata.create_all(target_engine or engine)
