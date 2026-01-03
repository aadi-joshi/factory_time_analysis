"""
Database models for VA/NVA tracking system
"""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()


class Video(Base):
    __tablename__ = "videos"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    fps = Column(Float, nullable=False)
    duration_sec = Column(Float, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    total_frames = Column(Integer, nullable=False)
    first_frame_path = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="uploaded")  # uploaded, processing, complete, failed
    
    tracks = relationship("Track", back_populates="video", cascade="all, delete-orphan")
    zones = relationship("Zone", back_populates="video", cascade="all, delete-orphan")
    worker_zone_mappings = relationship("WorkerZoneMapping", back_populates="video", cascade="all, delete-orphan")
    id_merges = relationship("IDMerge", back_populates="video", cascade="all, delete-orphan")
    metrics = relationship("VANVAMetric", back_populates="video", cascade="all, delete-orphan")


class Track(Base):
    __tablename__ = "tracks"
    
    id = Column(Integer, primary_key=True)
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    frame_idx = Column(Integer, nullable=False)
    track_id = Column(Integer, nullable=False)
    bbox_x1 = Column(Float, nullable=False)
    bbox_y1 = Column(Float, nullable=False)
    bbox_x2 = Column(Float, nullable=False)
    bbox_y2 = Column(Float, nullable=False)
    centroid_x = Column(Float, nullable=False)
    centroid_y = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    
    video = relationship("Video", back_populates="tracks")


class Zone(Base):
    __tablename__ = "zones"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    label = Column(String, nullable=False)
    polygon_json = Column(Text, nullable=False)  # JSON array: [[x1,y1], [x2,y2], ...]
    color = Column(String, default="#FF5733")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    video = relationship("Video", back_populates="zones")
    mappings = relationship("WorkerZoneMapping", back_populates="zone", cascade="all, delete-orphan")


class WorkerZoneMapping(Base):
    __tablename__ = "worker_zone_mapping"
    
    id = Column(Integer, primary_key=True)
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    worker_id = Column(String, nullable=False)  # original track_id or merged_worker_id
    zone_id = Column(String, ForeignKey("zones.id"), nullable=False)
    is_va = Column(Boolean, default=True)  # TRUE = VA, FALSE = NVA
    
    video = relationship("Video", back_populates="worker_zone_mappings")
    zone = relationship("Zone", back_populates="mappings")


class IDMerge(Base):
    __tablename__ = "id_merges"
    
    id = Column(Integer, primary_key=True)
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    merged_worker_id = Column(String, nullable=False)
    original_track_ids = Column(Text, nullable=False)  # JSON array: [3, 7, 12]
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    video = relationship("Video", back_populates="id_merges")


class VANVAMetric(Base):
    __tablename__ = "vava_metrics"
    
    id = Column(Integer, primary_key=True)
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    worker_id = Column(String, nullable=False)
    va_frames = Column(Integer, default=0)
    nva_frames = Column(Integer, default=0)
    va_seconds = Column(Float, default=0.0)
    nva_seconds = Column(Float, default=0.0)
    va_percentage = Column(Float, default=0.0)
    computed_at = Column(DateTime, default=datetime.utcnow)
    
    video = relationship("Video", back_populates="metrics")
