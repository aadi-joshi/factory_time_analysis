"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db, engine
from sqlmodel import Session
import sqlite3
from .routes.videos import router as videos_router
from .routes.persons import router as persons_router

app = FastAPI(title="Factory Time Analyzer", version="0.1.0")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()
    # lightweight migration for new PersonTrack columns
    with Session(engine) as session:
        try:
            conn = sqlite3.connect("backend/data/app.db")
            cur = conn.cursor()
            # detect columns
            cur.execute("PRAGMA table_info(persontrack);")
            cols = [r[1] for r in cur.fetchall()]
            if 'thumbnail_path' not in cols:
                cur.execute("ALTER TABLE persontrack ADD COLUMN thumbnail_path TEXT")
            if 'feature_json' not in cols:
                cur.execute("ALTER TABLE persontrack ADD COLUMN feature_json TEXT")
            conn.commit(); conn.close()
        except Exception:
            pass

app.include_router(videos_router)
app.include_router(persons_router)

@app.get("/health")
def health():
    return {"status": "ok"}
