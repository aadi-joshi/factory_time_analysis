"""
Pydantic models for API requests/responses
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


# ==================== Video ====================
class VideoUploadResponse(BaseModel):
    id: str
    filename: str
    fps: float
    duration_sec: float
    width: int
    height: int
    total_frames: int
    first_frame_path: Optional[str] = None
    status: str
    uploaded_at: datetime


class VideoMetadata(BaseModel):
    id: str
    filename: str
    fps: float
    duration_sec: float
    width: int
    height: int
    total_frames: int
    status: str
    uploaded_at: datetime


# ==================== Zones ====================
class ZoneCreate(BaseModel):
    video_id: str
    label: str
    polygon: List[List[float]] = Field(..., description="List of [x, y] coordinates")
    color: str = "#FF5733"


class ZoneResponse(BaseModel):
    id: str
    video_id: str
    label: str
    polygon: List[List[float]]
    color: str
    created_at: datetime


# ==================== Tracking ====================
class BboxCoords(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class TrackData(BaseModel):
    frame_idx: int
    track_id: int
    bbox: List[float]  # [x1, y1, x2, y2]
    centroid: List[float]  # [cx, cy]
    confidence: float


class FrameTracksResponse(BaseModel):
    frame_idx: int
    tracks: List[TrackData]


class ProcessingStartResponse(BaseModel):
    video_id: str
    status: str
    message: str


# ==================== Worker-Zone Mapping ====================
class WorkerZoneAssignmentCreate(BaseModel):
    video_id: str
    worker_id: str
    zone_id: str
    is_va: bool = True


class WorkerZoneAssignmentResponse(BaseModel):
    id: int
    video_id: str
    worker_id: str
    zone_id: str
    is_va: bool


class WorkerZonesResponse(BaseModel):
    worker_id: str
    va_zones: List[str]
    nva_zones: List[str]


# ==================== ID Merge ====================
class IDMergeCreate(BaseModel):
    video_id: str
    merged_worker_id: str
    original_track_ids: List[int]
    notes: Optional[str] = None


class IDMergeResponse(BaseModel):
    id: int
    video_id: str
    merged_worker_id: str
    original_track_ids: List[int]
    notes: Optional[str]
    created_at: datetime


# ==================== Metrics ====================
class VANVAMetricData(BaseModel):
    worker_id: str
    va_frames: int
    nva_frames: int
    va_seconds: float
    nva_seconds: float
    va_percentage: float


class MetricsResponse(BaseModel):
    video_id: str
    metrics: List[VANVAMetricData]


class WorkerTimelinePoint(BaseModel):
    frame_idx: int
    centroid: List[float]
    is_va: bool
    zone_id: Optional[str] = None


class WorkerTimelineResponse(BaseModel):
    worker_id: str
    timeline: List[WorkerTimelinePoint]


# ==================== Summary ====================
class WorkerSummary(BaseModel):
    worker_id: str
    first_frame: int
    last_frame: int
    total_frames: int


class VideoProcessingSummary(BaseModel):
    video_id: str
    status: str
    total_workers: int
    workers: List[WorkerSummary]
