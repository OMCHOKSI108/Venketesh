from typing import Generator
from sqlalchemy.orm import Session
from app.services.database import get_db
from app.config import get_settings


def get_database() -> Generator[Session, None, None]:
    return get_db()
