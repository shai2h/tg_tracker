import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не указан")

if "+asyncpg" in DATABASE_URL:
    raise RuntimeError("Sync sqlalchemy проверьте DATABASE_URL postgresql+psycorg://")

engine = create_engine(DATABASE_URL, echo=True)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def create_tables():
    # обычно миграциями занимаются
    Base.metadata.create_all(bind=engine)


def get_db():
    # паттерн получения сесси 2 - генератор. это правильный Фаст АПИШный паттерн
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()