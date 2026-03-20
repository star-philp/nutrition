from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from app.core.config import settings

engine = create_engine(
    settings.get_database_url, 
    connect_args={"options": "-c client_encoding=utf8"}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# FastAPI에서 의존성 주입으로 사용될 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 