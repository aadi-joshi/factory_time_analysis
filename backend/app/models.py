"""Database models."""
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

class Video(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    original_name: str
    fps: float
    frame_count: int
    duration_seconds: float
    created_at: datetime = Field(default_factory=datetime.utcnow)

    zones: List["Zone"] = Relationship(back_populates="video")
    tracks: List["PersonTrack"] = Relationship(back_populates="video")

class Zone(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="video.id")
    name: str
    points_json: str  # JSON list of {x,y}
    created_at: datetime = Field(default_factory=datetime.utcnow)

    video: Optional[Video] = Relationship(back_populates="zones")

class PersonTrack(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="video.id")
    internal_track_id: int  # YOLO tracker id
    display_name: str
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    thumbnail_path: Optional[str] = Field(default=None, description="Path to representative thumbnail image")
    feature_json: Optional[str] = Field(default=None, description="Serialized appearance feature (e.g., color histogram)")

    video: Optional[Video] = Relationship(back_populates="tracks")
    points: List["TrackPoint"] = Relationship(back_populates="person")

class TrackPoint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    person_track_id: int = Field(foreign_key="persontrack.id")
    frame_index: int
    timestamp: float  # seconds
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    centroid_x: float
    centroid_y: float
    value_added: bool
    zone_id: Optional[int] = Field(default=None, foreign_key="zone.id")

    person: Optional[PersonTrack] = Relationship(back_populates="points")
