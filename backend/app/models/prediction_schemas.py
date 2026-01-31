"""
Pydantic models for Action Prediction API
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PredictionUploadResponse(BaseModel):
    """Response after uploading video for prediction"""
    job_id: str
    filename: str
    message: str


class PredictionStatus(BaseModel):
    """Prediction job status"""
    job_id: str
    status: str  # pending, processing, complete, failed
    progress: Optional[int] = None  # 0-100
    message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class PredictionResult(BaseModel):
    """Prediction results"""
    coarse_action: str
    fine_action: str
    value_category: str  # VA, RNVA, NVA, UNKNOWN
    duration: float
    fps: float


class PredictionJobInfo(BaseModel):
    """Complete prediction job information"""
    job_id: str
    filename: str
    status: str
    progress: Optional[int] = None
    result: Optional[PredictionResult] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    input_video_path: Optional[str] = None
    output_video_path: Optional[str] = None
