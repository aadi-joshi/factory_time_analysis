"""
Script to create PostgreSQL database
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from app.config import settings

def create_database():
    """Create the PostgreSQL database if it doesn't exist"""
    try:
        # Connect to PostgreSQL server (default 'postgres' database)
        conn = psycopg2.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            database='postgres'  # Connect to default database first
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{settings.postgres_db}'")
        exists = cursor.fetchone()
        
        if not exists:
            print(f"Creating database '{settings.postgres_db}'...")
            cursor.execute(f'CREATE DATABASE {settings.postgres_db}')
            print(f"✅ Database '{settings.postgres_db}' created successfully!")
        else:
            print(f"✅ Database '{settings.postgres_db}' already exists")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Error creating database: {e}")
        return False

if __name__ == "__main__":
    create_database()
