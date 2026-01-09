"""
Database session management for dual-storage setup
SQLite: Primary storage (all tables)
PostgreSQL: Backup storage (videos + metrics only)
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.db.models import Base, PostgresBase
from app.config import settings

# ==================== SQLite Engine (Primary Storage - ALL DATA) ====================
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), settings.sqlite_db_path)
sqlite_url = f"sqlite:///{DB_PATH}"

sqlite_engine = create_engine(
    sqlite_url,
    connect_args={"check_same_thread": False},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)


# ==================== PostgreSQL Engine (Backup Storage - VIDEOS + METRICS ONLY) ====================
postgres_url = f"postgresql://{settings.postgres_user}:{settings.postgres_password}@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"

postgres_engine = create_engine(
    postgres_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

PostgresSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=postgres_engine)


# ==================== Database Initialization ====================
def init_db():
    """Initialize both databases"""
    print("Initializing SQLite database (primary storage)...")
    Base.metadata.create_all(bind=sqlite_engine)
    print("✅ SQLite tables created (all tables)")
    
    print("Initializing PostgreSQL database (backup storage)...")
    PostgresBase.metadata.create_all(bind=postgres_engine)
    print("✅ PostgreSQL tables created (videos + metrics backup)")


# ==================== Dependency Injection ====================
def get_db() -> Session:
    """Get SQLite session (primary database)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_postgres_db() -> Session:
    """Get PostgreSQL session (backup database)"""
    db = PostgresSessionLocal()
    try:
        yield db
    finally:
        db.close()
