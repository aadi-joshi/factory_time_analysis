"""Pydantic / SQLModel response and request schemas."""
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class ZonePoint(BaseModel):
    x: float
    y: float

class ZoneCreate(BaseModel):
    name: str
    points: List[ZonePoint]

class ZoneRead(BaseModel):
    id: int
    name: str
    points: List[ZonePoint]
    class Config:
        orm_mode = True

class VideoRead(BaseModel):
    id: int
    filename: str
    original_name: str
    fps: float
    frame_count: int
    duration_seconds: float
    created_at: datetime
    class Config:
        orm_mode = True

class VideoListItem(VideoRead):
    pass

class PersonSummary(BaseModel):
    person_id: int
    internal_track_id: int
    name: str
    total_time_seconds: float
    value_added_seconds: float
    non_value_added_seconds: float
    value_added_ratio: float

class PersonRename(BaseModel):
    name: str

class MergePersonsRequest(BaseModel):
    from_id: int
    into_id: int

class FrameTrackBBox(BaseModel):
    person_id: int
    display_name: str
    internal_track_id: int
    frame_index: int
    value_added: bool
    bbox: List[float]  # x,y,w,h

class FrameDataResponse(BaseModel):
    frame_index: int
    persons: List[FrameTrackBBox]
    zones: List[ZoneRead]

class ProcessVideoResponse(BaseModel):
    status: str
    processed_frames: int
    persons_detected: int

class UploadVideoResponse(VideoRead):
    pass
