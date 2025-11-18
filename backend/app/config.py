"""Application configuration loading from environment variables.
"""
from pydantic import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    environment: str = "dev"
    detection_conf: float = 0.25
    iou: float = 0.45
    process_frame_stride: int = 1  # process every Nth frame
    data_dir: str = "backend/data"
    video_storage_dir: str = "backend/data/videos"
    database_url: str = "sqlite:///backend/data/app.db"
    max_video_length_minutes: int = 30
    thumbnail_dir: str = "backend/data/thumbnails"  # stored person thumbnails
    tracker_type: str = "bytetrack"  # can be 'bytetrack' | 'strongsort' | 'deepsort' (if installed)
    merge_hist_threshold: float = 0.9  # appearance correlation threshold to merge fragmented IDs
    merge_iou_threshold: float = 0.3   # IoU threshold for considering same person
    zone_overlap_threshold: float = 0.2  # fraction of bbox overlapped by zone to mark value-added

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
