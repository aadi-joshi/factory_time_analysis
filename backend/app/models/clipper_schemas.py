"""
Pydantic schemas for Video Clipper feature
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class VideoClipperJobResponse(BaseModel):
    """Response when creating a new video clipper job"""
    job_id: str
    status: str
    message: str


class ClipInfo(BaseModel):
    """Information about a generated clip"""
    filename: str
    folder: str
    action_name: str
    va_tag: str
    clip_number: int
    duration_sec: float
    download_url: str


class ClipperJobStatus(BaseModel):
    """Status of a video clipper job"""
    job_id: str
    status: str  # 'pending', 'processing', 'complete', 'failed'
    progress: Optional[int] = None  # Percentage 0-100
    total_clips: Optional[int] = None
    processed_clips: Optional[int] = None
    clips: Optional[List[ClipInfo]] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
