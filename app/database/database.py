import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Setup Database Engine
# connect_args to check_same_thread is necessary only for SQLite
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    sqlite_path = settings.DATABASE_URL.replace("sqlite:///", "", 1)
    sqlite_dir = os.path.dirname(sqlite_path)
    if sqlite_dir and not os.path.isdir(sqlite_dir):
        os.makedirs(sqlite_dir, exist_ok=True)
else:
    connect_args = {}

engine = create_engine(
    
    settings.DATABASE_URL, 
    connect_args=connect_args,
    # pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
