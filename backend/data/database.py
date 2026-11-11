
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL,pool_pre_ping=True,)

SessionLocal = sessionmaker(bind=engine,expire_on_commit=False,)


class Base(DeclarativeBase):
    pass

def create_database():
    from backend.data import database_model 
    Base.metadata.create_all(bind=engine)



