"""
Configuration management for dual-database setup
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # PostgreSQL Configuration (Permanent Storage)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str
    postgres_db: str = "vanva_db"
    
    # SQLite Configuration (Temporary Storage)
    sqlite_db_path: str = "tracking.db"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
