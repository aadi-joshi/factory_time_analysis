"""
Main FastAPI application
"""
import os
from typing import Dict
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pathlib import Path
import uuid
import json

from app.db import init_db, get_db, get_postgres_db
from app.db.models import Video, Track, Zone, WorkerZoneMapping, IDMerge, VANVAMetric
from app.db.models import VideoBackup, VANVAMetricBackup  # PostgreSQL backup models
from app.models.schemas import *
from app.ml_pipelines.zone_worker_tracker import (
    DetectionService,
    VideoProcessingService,
    ZoneGeometry,
    VANVACalculator
)

# Initialize FastAPI app
app = FastAPI(title="VA/NVA Worker Analysis System", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
init_db()

# Setup paths
BASE_DIR = Path(__file__).parent.parent.parent
STORAGE_DIR = BASE_DIR / "storage"
VIDEOS_DIR = STORAGE_DIR / "videos"
FRAMES_DIR = STORAGE_DIR / "frames"
PORTRAITS_DIR = STORAGE_DIR / "portraits"
DATASET_DIR = STORAGE_DIR / "dataset"

VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)
PORTRAITS_DIR.mkdir(parents=True, exist_ok=True)
DATASET_DIR.mkdir(parents=True, exist_ok=True)

# Initialize ML services
detector = DetectionService(model_path="yolov8n.pt", device="cpu")
video_processor = VideoProcessingService(detector)

# Initialize Video Clipper service
from app.services.video_clipper_service import VideoClipperService
from app.models.clipper_schemas import VideoClipperJobResponse, ClipperJobStatus, ClipInfo

video_clipper = VideoClipperService(STORAGE_DIR)

# Store for tracking clipper jobs (in production, use database)
clipper_jobs = {}

# Initialize Action Prediction service
from app.services.action_prediction_service import ActionPredictionService
from app.models.prediction_schemas import (
    PredictionUploadResponse,
    PredictionStatus,
    PredictionResult,
    PredictionJobInfo
)

# Lazy-load prediction service (heavy ML models)
prediction_service = None
prediction_jobs = {}

def get_prediction_service():
    """Lazy-load prediction service to avoid startup delay"""
    global prediction_service
    if prediction_service is None:
        print("🔧 Initializing Action Prediction Service...")
        prediction_service = ActionPredictionService()
    return prediction_service




# ==================== Video Deletion ====================

@app.delete("/api/videos/{video_id}")
def delete_video(video_id: str, db: Session = Depends(get_db)):
    """Delete a video and all associated data"""
    db_video = db.query(Video).filter(Video.id == video_id).first()
    if not db_video:
        raise HTTPException(status_code=404, detail="Video not found")
    db.delete(db_video)
    db.commit()
    return {"status": "deleted", "video_id": video_id}


# ==================== Video Management ====================

@app.post("/api/videos/upload", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    postgres_db: Session = Depends(get_postgres_db)
):
    """Upload a video file"""
    try:
        # Generate unique video ID
        video_id = str(uuid.uuid4())
        
        # Save uploaded file
        file_path = VIDEOS_DIR / f"{video_id}.mp4"
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Extract metadata
        import cv2
        cap = cv2.VideoCapture(str(file_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        
        duration_sec = total_frames / fps if fps > 0 else 0
        
        # Extract first frame
        first_frame_path = FRAMES_DIR / f"{video_id}_first.jpg"
        video_processor.extract_first_frame(str(file_path), str(first_frame_path))
        
        # Save to SQLite database (primary storage)
        db_video = Video(
            id=video_id,
            filename=file.filename,
            fps=fps,
            duration_sec=duration_sec,
            width=width,
            height=height,
            total_frames=total_frames,
            first_frame_path=str(first_frame_path),
            status="uploaded"
        )
        db.add(db_video)
        db.commit()
        db.refresh(db_video)
        
        # Also save to PostgreSQL (permanent backup)
        postgres_video = VideoBackup(
            id=video_id,
            filename=file.filename,
            fps=fps,
            duration_sec=duration_sec,
            width=width,
            height=height,
            total_frames=total_frames,
            first_frame_path=str(first_frame_path),
            status="uploaded"
        )
        postgres_db.add(postgres_video)
        postgres_db.commit()
        
        print(f"✅ Saved video {video_id} to SQLite and PostgreSQL backup")
        
        return VideoUploadResponse(
            id=db_video.id,
            filename=db_video.filename,
            fps=db_video.fps,
            duration_sec=db_video.duration_sec,
            width=db_video.width,
            height=db_video.height,
            total_frames=db_video.total_frames,
            first_frame_path=str(first_frame_path),
            status=db_video.status,
            uploaded_at=db_video.uploaded_at
        )
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/videos/{video_id}", response_model=VideoMetadata)
def get_video(video_id: str, db: Session = Depends(get_db)):
    """Get video metadata"""
    db_video = db.query(Video).filter(Video.id == video_id).first()
    if not db_video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return VideoMetadata(
        id=db_video.id,
        filename=db_video.filename,
        fps=db_video.fps,
        duration_sec=db_video.duration_sec,
        width=db_video.width,
        height=db_video.height,
        total_frames=db_video.total_frames,
        status=db_video.status,
        uploaded_at=db_video.uploaded_at
    )


@app.get("/api/videos")
def list_videos(db: Session = Depends(get_db)):
    """List all videos"""
    videos = db.query(Video).all()
    return {
        "videos": [
            {
                "id": v.id,
                "filename": v.filename,
                "duration_sec": v.duration_sec,
                "status": v.status,
                "uploaded_at": v.uploaded_at.isoformat()
            }
            for v in videos
        ]
    }


@app.get("/api/videos/{video_id}/first-frame")
def get_first_frame(video_id: str, db: Session = Depends(get_db)):
    """Get first frame as image"""
    db_video = db.query(Video).filter(Video.id == video_id).first()
    if not db_video or not db_video.first_frame_path:
        raise HTTPException(status_code=404, detail="First frame not found")
    
    return FileResponse(db_video.first_frame_path, media_type="image/jpeg")


@app.get("/api/videos/{video_id}/workers/{worker_id}/image")
def get_worker_image(video_id: str, worker_id: str):
    """Serve the representative portrait image for a worker, if it exists."""
    portrait_path = PORTRAITS_DIR / video_id / f"{worker_id}.jpg"
    if not portrait_path.exists():
        raise HTTPException(status_code=404, detail="Worker image not found")

    return FileResponse(str(portrait_path), media_type="image/jpeg")


@app.get("/api/videos/{video_id}/workers/{worker_id}/first-detection-frame")
def get_worker_first_detection_frame(video_id: str, worker_id: str, db: Session = Depends(get_db)):
    """Return the first frame where this worker was detected, with a single bounding box overlay.

    This helps the UI clearly show which physical person a worker/track ID refers to
    when performing merge operations.
    """
    # Look up the earliest track entry for this worker in this video
    try:
        worker_int = int(worker_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="worker_id must be an integer track id")

    track = (
        db.query(Track)
        .filter(Track.video_id == video_id, Track.track_id == worker_int)
        .order_by(Track.frame_idx.asc())
        .first()
    )

    if not track:
        raise HTTPException(status_code=404, detail="No tracking data found for this worker")

    video_path = VIDEOS_DIR / f"{video_id}.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    # Lazy import to avoid unnecessary global dependency at startup
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    import io

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Unable to open video file")

    # frame_idx is zero-based as stored during processing
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(track.frame_idx))
    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        raise HTTPException(status_code=500, detail="Unable to read frame for worker")

    # Draw a single colored box only for this worker's bbox
    x1 = int(track.bbox_x1)
    y1 = int(track.bbox_y1)
    x2 = int(track.bbox_x2)
    y2 = int(track.bbox_y2)

    # Clamp to frame bounds for safety
    h, w = frame.shape[:2]
    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(0, min(x2, w))
    y2 = max(0, min(y2, h))

    if x2 > x1 and y2 > y1:
        color = (0, 255, 0)  # bright green box
        thickness = max(2, min(h, w) // 200)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

        # Optional label to reinforce which worker this is
        label = f"ID {worker_int}"
        cv2.putText(
            frame,
            label,
            (x1, max(0, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
            cv2.LINE_AA,
        )

    # Encode as JPEG in-memory
    success, buffer = cv2.imencode(".jpg", frame)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode preview image")

    bytes_io = io.BytesIO(buffer.tobytes())
    return StreamingResponse(bytes_io, media_type="image/jpeg")


# ==================== Processing ====================

import threading 

@app.post("/api/videos/{video_id}/process")
def process_video(video_id: str, db: Session = Depends(get_db)):
    db_video = db.query(Video).filter(Video.id == video_id).first()
    if not db_video:
        raise HTTPException(status_code=404, detail="Video not found")

    db_video.status = "processing"
    db.commit()

    video_path = VIDEOS_DIR / f"{video_id}.mp4"

    threading.Thread(
        target=process_video_background,
        args=(video_id, str(video_path)),
        daemon=True
    ).start()

    return {
        "video_id": video_id,
        "status": "processing"
    }



def process_video_background(video_id: str, video_path: str):
    from app.db import SessionLocal
    import traceback

    print(f"[PROCESS] Started {video_id}")

    db = SessionLocal()
    try:
        # Directory to store per-worker portrait crops
        portraits_dir = PORTRAITS_DIR / video_id
        portraits_dir.mkdir(parents=True, exist_ok=True)

        all_tracks, _ = video_processor.process_video(
            video_path,
            portraits_dir=str(portraits_dir),
        )

        for frame_data in all_tracks:
            for track in frame_data["tracks"]:
                db.add(Track(
                    video_id=video_id,
                    frame_idx=frame_data["frame_idx"],
                    track_id=track["track_id"],
                    bbox_x1=track["bbox"][0],
                    bbox_y1=track["bbox"][1],
                    bbox_x2=track["bbox"][2],
                    bbox_y2=track["bbox"][3],
                    centroid_x=track["centroid"][0],
                    centroid_y=track["centroid"][1],
                    confidence=track["confidence"]
                ))

        db.commit()

        db_video = db.query(Video).filter(Video.id == video_id).first()
        if db_video:
            db_video.status = "complete"
            db.commit()
            print(f"[PROCESS] COMPLETE {video_id}")

    except Exception as e:
        print("[PROCESS ERROR]", e)
        traceback.print_exc()

        db_video = db.query(Video).filter(Video.id == video_id).first()
        if db_video:
            db_video.status = "failed"
            db.commit()
    finally:
        db.close()



@app.get("/api/videos/{video_id}/summary", response_model=VideoProcessingSummary)
def get_processing_summary(video_id: str, db: Session = Depends(get_db)):
    """Get processing summary with worker list"""
    db_video = db.query(Video).filter(Video.id == video_id).first()
    if not db_video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    tracks = db.query(Track).filter(Track.video_id == video_id).all()
    
    worker_info = {}
    for track in tracks:
        worker_id = track.track_id
        if worker_id not in worker_info:
            worker_info[worker_id] = {
                "first_frame": track.frame_idx,
                "last_frame": track.frame_idx,
                "frames": 0
            }
        worker_info[worker_id]["last_frame"] = max(worker_info[worker_id]["last_frame"], track.frame_idx)
        worker_info[worker_id]["frames"] += 1
    
    workers = [
        WorkerSummary(
            worker_id=str(wid),
            first_frame=info["first_frame"],
            last_frame=info["last_frame"],
            total_frames=info["frames"]
        )
        for wid, info in worker_info.items()
    ]
    
    return VideoProcessingSummary(
        video_id=video_id,
        status=db_video.status,
        total_workers=len(workers),
        workers=workers
    )


@app.get("/api/videos/{video_id}/workers")
def list_workers(video_id: str, db: Session = Depends(get_db)):
    """Return all detected workers with basic stats and portrait image URLs."""
    db_video = db.query(Video).filter(Video.id == video_id).first()
    if not db_video:
        raise HTTPException(status_code=404, detail="Video not found")

    tracks = db.query(Track).filter(Track.video_id == video_id).all()
    if not tracks:
        return {"video_id": video_id, "workers": []}

    # --- Get all merges for this video ---
    merges = db.query(IDMerge).filter(IDMerge.video_id == video_id).all()
    orig_to_merged = {}  # original_track_id (str) -> merged_worker_id (str)
    merged_to_orig = {}  # merged_worker_id (str) -> set of original_track_ids (str)
    for m in merges:
        merged_id = m.merged_worker_id
        orig_ids = json.loads(m.original_track_ids)
        for oid in orig_ids:
            orig_to_merged[str(oid)] = merged_id
        if merged_id not in merged_to_orig:
            merged_to_orig[merged_id] = set()
        merged_to_orig[merged_id].update([str(oid) for oid in orig_ids])

    # --- Build info for all tracks ---
    worker_info = {}
    for track in tracks:
        worker_id = str(track.track_id)
        # If this worker_id was merged away, skip it (will show as merged_worker_id instead)
        if worker_id in orig_to_merged:
            continue
        if worker_id not in worker_info:
            worker_info[worker_id] = {
                "first_frame": track.frame_idx,
                "last_frame": track.frame_idx,
                "frames": 0,
            }
        info = worker_info[worker_id]
        info["last_frame"] = max(info["last_frame"], track.frame_idx)
        info["frames"] += 1

    # --- Add merged workers ---
    for merged_id, orig_ids in merged_to_orig.items():
        # Find all tracks for these original IDs
        merged_tracks = [t for t in tracks if str(t.track_id) in orig_ids]
        if not merged_tracks:
            continue
        first_frame = min(t.frame_idx for t in merged_tracks)
        last_frame = max(t.frame_idx for t in merged_tracks)
        total_frames = len(merged_tracks)
        # Use portrait of first original if available
        portrait_path = PORTRAITS_DIR / video_id / f"{list(orig_ids)[0]}.jpg"
        has_image = portrait_path.exists()
        worker_info[merged_id] = {
            "first_frame": first_frame,
            "last_frame": last_frame,
            "frames": total_frames,
            "merged_from": list(orig_ids),
            "image_url": f"/api/videos/{video_id}/workers/{list(orig_ids)[0]}/image" if has_image else None,
        }

    # --- Build response ---
    workers = []
    for wid, info in worker_info.items():
        w = {
            "worker_id": str(wid),
            "first_frame": info["first_frame"],
            "last_frame": info["last_frame"],
            "total_frames": info["frames"],
            "image_url": info.get("image_url"),
        }
        if "merged_from" in info:
            w["merged_from"] = info["merged_from"]
        workers.append(w)

    return {"video_id": video_id, "workers": workers}


# ==================== Zones ====================

@app.post("/api/zones", response_model=ZoneResponse)
def create_zone(zone_data: ZoneCreate, db: Session = Depends(get_db)):
    """Create a zone"""
    zone_id = str(uuid.uuid4())
    polygon_json = json.dumps(zone_data.polygon)
    
    db_zone = Zone(
        id=zone_id,
        video_id=zone_data.video_id,
        label=zone_data.label,
        polygon_json=polygon_json,
        color=zone_data.color
    )
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    
    return ZoneResponse(
        id=db_zone.id,
        video_id=db_zone.video_id,
        label=db_zone.label,
        polygon=json.loads(db_zone.polygon_json),
        color=db_zone.color,
        created_at=db_zone.created_at
    )


@app.get("/api/videos/{video_id}/zones")
def get_zones(video_id: str, db: Session = Depends(get_db)):
    """Get all zones for a video"""
    zones = db.query(Zone).filter(Zone.video_id == video_id).all()
    
    return {
        "zones": [
            {
                "id": z.id,
                "label": z.label,
                "polygon": json.loads(z.polygon_json),
                "color": z.color
            }
            for z in zones
        ]
    }


# ==================== Worker-Zone Mapping ====================

@app.post("/api/worker-zones/assign", response_model=WorkerZoneAssignmentResponse)
def assign_worker_zone(assignment: WorkerZoneAssignmentCreate, db: Session = Depends(get_db)):
    """Assign a zone to a worker"""
    db_assignment = WorkerZoneMapping(
        video_id=assignment.video_id,
        worker_id=assignment.worker_id,
        zone_id=assignment.zone_id,
        is_va=assignment.is_va
    )
    db.add(db_assignment)
    db.commit()
    db.refresh(db_assignment)
    
    return WorkerZoneAssignmentResponse(
        id=db_assignment.id,
        video_id=db_assignment.video_id,
        worker_id=db_assignment.worker_id,
        zone_id=db_assignment.zone_id,
        is_va=db_assignment.is_va
    )


@app.get("/api/videos/{video_id}/worker-zones")
def get_worker_zones(video_id: str, db: Session = Depends(get_db)):
    """Get worker-zone mappings"""
    mappings = db.query(WorkerZoneMapping).filter(WorkerZoneMapping.video_id == video_id).all()
    
    workers_dict = {}
    for mapping in mappings:
        if mapping.worker_id not in workers_dict:
            workers_dict[mapping.worker_id] = {"va_zones": [], "nva_zones": []}
        
        if mapping.is_va:
            workers_dict[mapping.worker_id]["va_zones"].append(mapping.zone_id)
        else:
            workers_dict[mapping.worker_id]["nva_zones"].append(mapping.zone_id)
    
    return {
        "worker_zones": [
            {
                "worker_id": wid,
                "va_zones": info["va_zones"],
                "nva_zones": info["nva_zones"]
            }
            for wid, info in workers_dict.items()
        ]
    }


# ==================== ID Merge ====================

@app.post("/api/id-merges", response_model=IDMergeResponse)
def create_id_merge(merge_data: IDMergeCreate, db: Session = Depends(get_db)):
    """Create an ID merge record"""
    original_ids_json = json.dumps(merge_data.original_track_ids)

    db_merge = IDMerge(
        video_id=merge_data.video_id,
        merged_worker_id=merge_data.merged_worker_id,
        original_track_ids=original_ids_json,
        notes=merge_data.notes
    )
    db.add(db_merge)
    db.commit()
    db.refresh(db_merge)

    # --- Update all relevant tables to use merged_worker_id ---
    orig_ids = [str(oid) for oid in merge_data.original_track_ids]
    merged_id = str(merge_data.merged_worker_id)

    # Update Track
    db.query(Track).filter(
        Track.video_id == merge_data.video_id,
        Track.track_id.in_(orig_ids)
    ).update({Track.track_id: merged_id}, synchronize_session=False)

    # Update WorkerZoneMapping
    db.query(WorkerZoneMapping).filter(
        WorkerZoneMapping.video_id == merge_data.video_id,
        WorkerZoneMapping.worker_id.in_(orig_ids)
    ).update({WorkerZoneMapping.worker_id: merged_id}, synchronize_session=False)

    # Update VANVAMetric
    db.query(VANVAMetric).filter(
        VANVAMetric.video_id == merge_data.video_id,
        VANVAMetric.worker_id.in_(orig_ids)
    ).update({VANVAMetric.worker_id: merged_id}, synchronize_session=False)

    db.commit()

    return IDMergeResponse(
        id=db_merge.id,
        video_id=db_merge.video_id,
        merged_worker_id=db_merge.merged_worker_id,
        original_track_ids=json.loads(db_merge.original_track_ids),
        notes=db_merge.notes,
        created_at=db_merge.created_at
    )


@app.get("/api/videos/{video_id}/id-merges")
def get_id_merges(video_id: str, db: Session = Depends(get_db)):
    """Get ID merge history"""
    merges = db.query(IDMerge).filter(IDMerge.video_id == video_id).all()
    
    return {
        "merges": [
            {
                "id": m.id,
                "merged_worker_id": m.merged_worker_id,
                "original_track_ids": json.loads(m.original_track_ids),
                "notes": m.notes,
                "created_at": m.created_at.isoformat()
            }
            for m in merges
        ]
    }


# ==================== Analytics ====================

@app.get("/api/videos/{video_id}/metrics")
def get_metrics(video_id: str, db: Session = Depends(get_db)):
    """Get VA/NVA metrics for video"""
    metrics = db.query(VANVAMetric).filter(VANVAMetric.video_id == video_id).all()
    
    return {
        "metrics": [
            {
                "worker_id": m.worker_id,
                "va_frames": m.va_frames,
                "nva_frames": m.nva_frames,
                "va_seconds": m.va_seconds,
                "nva_seconds": m.nva_seconds,
                "va_percentage": m.va_percentage
            }
            for m in metrics
        ]
    }


@app.post("/api/videos/{video_id}/compute-metrics")
def compute_metrics(
    video_id: str,
    db: Session = Depends(get_db),
    postgres_db: Session = Depends(get_postgres_db)
):
    """Compute VA/NVA metrics based on current configuration"""
    try:
        # Get video
        db_video = db.query(Video).filter(Video.id == video_id).first()
        if not db_video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get all tracks
        tracks = db.query(Track).filter(Track.video_id == video_id).all()
        if not tracks:
            raise HTTPException(status_code=400, detail="No tracking data available")
        
        # Organize tracks by frame
        tracks_by_frame = {}
        for track in tracks:
            if track.frame_idx not in tracks_by_frame:
                tracks_by_frame[track.frame_idx] = {"frame_idx": track.frame_idx, "tracks": []}
            
            tracks_by_frame[track.frame_idx]["tracks"].append({
                "track_id": track.track_id,
                "bbox": [track.bbox_x1, track.bbox_y1, track.bbox_x2, track.bbox_y2],
                "centroid": [track.centroid_x, track.centroid_y],
                "confidence": track.confidence
            })
        
        frames_list = list(sorted(tracks_by_frame.values(), key=lambda x: x["frame_idx"]))
        
        # Get zones
        zones = db.query(Zone).filter(Zone.video_id == video_id).all()
        zone_data = {z.id: {"polygon_json": z.polygon_json} for z in zones}
        
        # Get worker-zone mappings
        mappings = db.query(WorkerZoneMapping).filter(WorkerZoneMapping.video_id == video_id).all()
        worker_va_zones = {}
        for mapping in mappings:
            if mapping.is_va:
                if mapping.worker_id not in worker_va_zones:
                    worker_va_zones[mapping.worker_id] = []
                worker_va_zones[mapping.worker_id].append(mapping.zone_id)
        
        # Calculate base metrics per raw worker (track_id)
        metrics = VANVACalculator.calculate_metrics(
            frames_list,
            worker_va_zones,
            db_video.fps,
            zone_data,
        )

        # Apply any ID merge operations so analytics reflect merged identities
        merges = db.query(IDMerge).filter(IDMerge.video_id == video_id).all()
        if merges:
            merged_metrics: Dict[str, Dict] = {}

            # Start with base metrics keyed by string worker_id
            for worker_id, metric in metrics.items():
                merged_metrics[str(worker_id)] = dict(metric)

            for merge in merges:
                merged_id = merge.merged_worker_id
                original_ids = json.loads(merge.original_track_ids)

                va_frames = 0
                nva_frames = 0

                # Include frames for the merged_id itself (if any)
                m_merged = merged_metrics.get(str(merged_id))
                if m_merged:
                    va_frames += m_merged.get("va_frames", 0)
                    nva_frames += m_merged.get("nva_frames", 0)

                for orig_id in original_ids:
                    key = str(orig_id)
                    m = merged_metrics.get(key)
                    if not m:
                        continue
                    va_frames += m.get("va_frames", 0)
                    nva_frames += m.get("nva_frames", 0)

                total_frames = va_frames + nva_frames
                va_seconds = va_frames / db_video.fps if db_video.fps > 0 else 0
                nva_seconds = nva_frames / db_video.fps if db_video.fps > 0 else 0
                va_percentage = (va_frames / total_frames * 100) if total_frames > 0 else 0

                merged_metrics[merged_id] = {
                    "va_frames": va_frames,
                    "nva_frames": nva_frames,
                    "va_seconds": va_seconds,
                    "nva_seconds": nva_seconds,
                    "va_percentage": va_percentage,
                }

                # Remove originals so we don't double-count
                for orig_id in original_ids:
                    merged_metrics.pop(str(orig_id), None)

            metrics = merged_metrics
        
        # Clear previous metrics for this video to avoid duplicates
        db.query(VANVAMetric).filter(VANVAMetric.video_id == video_id).delete()
        postgres_db.query(VANVAMetricBackup).filter(VANVAMetricBackup.video_id == video_id).delete()

        # Store metrics in SQLite (primary storage)
        for worker_id, metric in metrics.items():
            db_metric = VANVAMetric(
                video_id=video_id,
                worker_id=str(worker_id),
                va_frames=metric["va_frames"],
                nva_frames=metric["nva_frames"],
                va_seconds=metric["va_seconds"],
                nva_seconds=metric["nva_seconds"],
                va_percentage=metric["va_percentage"]
            )
            db.add(db_metric)
            
            # Also save to PostgreSQL (permanent backup)
            postgres_metric = VANVAMetricBackup(
                video_id=video_id,
                worker_id=str(worker_id),
                va_frames=metric["va_frames"],
                nva_frames=metric["nva_frames"],
                va_seconds=metric["va_seconds"],
                nva_seconds=metric["nva_seconds"],
                va_percentage=metric["va_percentage"]
            )
            postgres_db.add(postgres_metric)
        
        db.commit()
        postgres_db.commit()
        
        print(f"✅ Saved {len(metrics)} metrics to SQLite and PostgreSQL backup")
        
        return {
            "video_id": video_id,
            "status": "success",
            "metrics_count": len(metrics)
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/videos/{video_id}/worker-timeline/{worker_id}")
def get_worker_timeline(video_id: str, worker_id: str, db: Session = Depends(get_db)):
    """Get timeline for a specific worker"""
    try:
        # Get worker-zone mappings
        mappings = db.query(WorkerZoneMapping).filter(
            WorkerZoneMapping.video_id == video_id,
            WorkerZoneMapping.worker_id == worker_id
        ).all()
        
        va_zones = {m.zone_id for m in mappings if m.is_va}
        
        # Get all zones data
        zones = db.query(Zone).filter(Zone.video_id == video_id).all()
        zone_data = {z.id: {"polygon_json": z.polygon_json} for z in zones}
        
        # Get tracks for this worker
        tracks = db.query(Track).filter(
            Track.video_id == video_id,
            Track.track_id == int(worker_id)
        ).order_by(Track.frame_idx).all()
        
        timeline = []
        for track in tracks:
            is_in_va = False
            zone_id = None
            
            for va_zone_id in va_zones:
                if va_zone_id in zone_data:
                    polygon = ZoneGeometry.polygon_from_json(zone_data[va_zone_id]["polygon_json"])
                    if ZoneGeometry.point_in_polygon((track.centroid_x, track.centroid_y), polygon):
                        is_in_va = True
                        zone_id = va_zone_id
                        break
            
            timeline.append({
                "frame_idx": track.frame_idx,
                "centroid": [track.centroid_x, track.centroid_y],
                "is_va": is_in_va,
                "zone_id": zone_id
            })
        
        return {
            "worker_id": worker_id,
            "timeline": timeline
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Video Clipper ====================

@app.post("/api/video-clipper/upload", response_model=VideoClipperJobResponse)
async def upload_video_clipper_files(
    video: UploadFile = File(...),
    excel: UploadFile = File(...)
):
    """Upload video and Excel file for clipping"""
    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Create temp directory for this job
        temp_dir = STORAGE_DIR / "temp" / job_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Save video file with original filename
        video_path = temp_dir / video.filename
        video_content = await video.read()
        with open(video_path, "wb") as f:
            f.write(video_content)
        
        # Save Excel file
        excel_path = temp_dir / excel.filename
        excel_content = await excel.read()
        with open(excel_path, "wb") as f:
            f.write(excel_content)
        
        # Validate Excel file
        try:
            video_clipper.parse_excel_timestamps(str(excel_path))
        except Exception as e:
            # Clean up temp files
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"Invalid Excel file: {str(e)}")
        
        # Initialize job status
        from datetime import datetime
        clipper_jobs[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "progress": 0,
            "total_clips": None,
            "processed_clips": 0,
            "clips": [],
            "error_message": None,
            "created_at": datetime.now(),
            "completed_at": None,
            "video_path": str(video_path),
            "excel_path": str(excel_path),
            "video_name": Path(video.filename).stem
        }
        
        # Start background processing
        threading.Thread(
            target=process_clipper_job_background,
            args=(job_id,),
            daemon=True
        ).start()
        
        return VideoClipperJobResponse(
            job_id=job_id,
            status="pending",
            message="Video clipper job started. Use job_id to check progress."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def process_clipper_job_background(job_id: str):
    """Background task to process video clipping"""
    import traceback
    from datetime import datetime
    
    print(f"[CLIPPER] Started job {job_id}")
    
    try:
        job = clipper_jobs[job_id]
        job["status"] = "processing"
        
        def progress_callback(progress, processed, total):
            job["progress"] = progress
            job["processed_clips"] = processed
            job["total_clips"] = total
        
        # Cut video
        result = video_clipper.cut_video_clips(
            video_path=job["video_path"],
            excel_path=job["excel_path"],
            job_id=job_id,
            progress_callback=progress_callback
        )
        
        # Update job with results
        job["status"] = "complete"
        job["progress"] = 100
        job["total_clips"] = result["total_clips"]
        job["processed_clips"] = result["total_clips"]
        job["clips"] = result["clips"]
        job["completed_at"] = datetime.now()
        
        print(f"[CLIPPER] COMPLETE {job_id} - {result['total_clips']} clips created")
        
        # Clean up temp files
        import shutil
        temp_dir = Path(job["video_path"]).parent
        shutil.rmtree(temp_dir, ignore_errors=True)
        
    except Exception as e:
        print(f"[CLIPPER ERROR] {job_id}:", e)
        traceback.print_exc()
        
        job = clipper_jobs.get(job_id)
        if job:
            job["status"] = "failed"
            job["error_message"] = str(e)
            job["completed_at"] = datetime.now()


@app.get("/api/video-clipper/jobs/{job_id}", response_model=ClipperJobStatus)
def get_clipper_job_status(job_id: str):
    """Get status of a video clipper job"""
    if job_id not in clipper_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = clipper_jobs[job_id]
    
    # Convert clips to ClipInfo objects
    clips = None
    if job["clips"]:
        clips = [
            ClipInfo(
                filename=clip["filename"],
                folder=clip["folder"],
                action_name=clip["action_name"],
                va_tag=clip["va_tag"],
                clip_number=clip["clip_number"],
                duration_sec=clip["duration_sec"],
                download_url=f"/api/video-clipper/clips/{job_id}/{clip['relative_path']}"
            )
            for clip in job["clips"]
        ]
    
    return ClipperJobStatus(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"],
        total_clips=job["total_clips"],
        processed_clips=job["processed_clips"],
        clips=clips,
        error_message=job["error_message"],
        created_at=job["created_at"],
        completed_at=job["completed_at"]
    )


@app.get("/api/video-clipper/clips/{job_id}/{video_name}/{filename}")
def download_clip(job_id: str, video_name: str, filename: str):
    """Download a specific clip"""
    # Clips are now stored directly in video_name folder (flat structure)
    clip_path = DATASET_DIR / video_name / filename
    
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail="Clip not found")
    
    return FileResponse(
        str(clip_path),
        media_type="video/mp4",
        filename=filename
    )


# ==================== Action Prediction ====================

PREDICTIONS_DIR = STORAGE_DIR / "predictions"
PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)

@app.post("/api/predict-action/upload", response_model=PredictionUploadResponse)
async def upload_prediction_video(
    video: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload video for action prediction"""
    try:
        # Validate file type
        if not video.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            raise HTTPException(status_code=400, detail="Invalid video format. Supported: MP4, AVI, MOV, MKV, WEBM")
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Create directory for this prediction job
        job_dir = PREDICTIONS_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # Save video file
        input_path = job_dir / "input.mp4"
        video_content = await video.read()
        with open(input_path, "wb") as f:
            f.write(video_content)
        
        # Create DB record
        from app.db.models import Prediction
        new_job = Prediction(
            job_id=job_id,
            filename=video.filename,
            status="pending",
            input_video_path=str(input_path)
        )
        db.add(new_job)
        db.commit()
        
        # Initialize in-memory progress tracker (since DB only stores status)
        prediction_jobs[job_id] = {
            "progress": 0,
            "error": None
        }
        
        return PredictionUploadResponse(
            job_id=job_id,
            filename=video.filename,
            message="Video uploaded successfully. Use /process endpoint to start prediction."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/predict-action/{job_id}/process")
def process_prediction(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Start prediction processing for uploaded video"""
    from app.db.models import Prediction
    
    # Check if job exists in DB
    job = db.query(Prediction).filter(Prediction.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != "pending":
        raise HTTPException(status_code=400, detail=f"Job already {job.status}")
    
    # Start background processing
    import threading
    threading.Thread(
        target=process_prediction_background,
        args=(job_id,),
        daemon=True
    ).start()
    
    # Update status immediately
    job.status = "processing"
    db.commit()
    
    # Init progress
    if job_id not in prediction_jobs:
        prediction_jobs[job_id] = {"progress": 0}
    prediction_jobs[job_id]["progress"] = 10
    
    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Prediction started"
    }


def process_prediction_background(job_id: str):
    """Background task to process action prediction"""
    import traceback
    from datetime import datetime
    from app.db import SessionLocal, PostgresSessionLocal
    from app.db.models import Prediction, PredictionBackup
    
    print(f"[PREDICTION] Started job {job_id}")
    db = SessionLocal()
    
    try:
        if job_id not in prediction_jobs:
            prediction_jobs[job_id] = {}
        
        prediction_jobs[job_id]["progress"] = 20
        
        # Get job record
        job = db.query(Prediction).filter(Prediction.job_id == job_id).first()
        if not job:
            return

        # Get prediction service
        service = get_prediction_service()
        
        # Run prediction
        prediction_jobs[job_id]["progress"] = 40
        prediction_result = service.predict_video(job.input_video_path)
        
        # Save prediction results
        job_dir = Path(job.input_video_path).parent
        prediction_path = job_dir / "prediction.json"
        with open(prediction_path, "w") as f:
            json.dump(prediction_result, f, indent=2)
        
        prediction_jobs[job_id]["progress"] = 60
        
        # Create annotated video
        output_path = job_dir / "output.mp4"
        success, actual_output_path = service.create_annotated_video(
            job.input_video_path,
            str(output_path),
            prediction_result
        )
        
        if not success:
            raise RuntimeError("Failed to create annotated video")
        
        prediction_jobs[job_id]["progress"] = 100
        
        # Update DB record with results
        job.status = "complete"
        job.output_video_path = actual_output_path
        job.coarse_action = prediction_result["coarse_action"]
        job.fine_action = prediction_result["fine_action"]
        job.value_category = prediction_result["value_category"]
        job.prediction_json = json.dumps(prediction_result)
        job.completed_at = datetime.now()
        
        db.commit()
        
        print(f"[PREDICTION] COMPLETE {job_id} - {prediction_result['fine_action']}")
        
        # Backup to PostgreSQL
        try:
            print(f"[PREDICTION] Backing up to PostgreSQL...")
            pg_db = PostgresSessionLocal()
            backup = PredictionBackup(
                id=str(uuid.uuid4()),
                job_id=job.job_id,
                filename=job.filename,
                status="complete",
                input_video_path=job.input_video_path,
                output_video_path=job.output_video_path,
                coarse_action=job.coarse_action,
                fine_action=job.fine_action,
                value_category=job.value_category,
                prediction_json=job.prediction_json,
                created_at=job.created_at,
                completed_at=job.completed_at
            )
            pg_db.add(backup)
            pg_db.commit()
            pg_db.close()
            print(f"[PREDICTION] PostgreSQL backup successful")
        except Exception as pg_e:
            print(f"[PREDICTION WARNING] PostgreSQL backup failed: {pg_e}")
            
    except Exception as e:
        print(f"[PREDICTION ERROR] {job_id}:", e)
        traceback.print_exc()
        
        # Update DB error
        try:
            job = db.query(Prediction).filter(Prediction.job_id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now()
                db.commit()
            
            if job_id in prediction_jobs:
                prediction_jobs[job_id]["error"] = str(e)
        except:
            pass
            
    finally:
        db.close()


@app.get("/api/predict-action/{job_id}/status", response_model=PredictionStatus)
def get_prediction_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Get status of a prediction job"""
    from app.db.models import Prediction
    
    job = db.query(Prediction).filter(Prediction.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get transient progress from memory if processing
    progress = 0
    if job.status == "processing" and job_id in prediction_jobs:
        progress = prediction_jobs[job_id].get("progress", 0)
    elif job.status == "complete":
        progress = 100
    
    return PredictionStatus(
        job_id=job.job_id,
        status=job.status,
        progress=progress,
        message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at
    )


@app.get("/api/predict-action/{job_id}/result", response_model=PredictionJobInfo)
def get_prediction_result(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Get prediction results"""
    from app.db.models import Prediction
    
    job = db.query(Prediction).filter(Prediction.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    result = None
    if job.prediction_json:
        result_dict = json.loads(job.prediction_json)
        result = PredictionResult(**result_dict)
    
    # Get transient progress from memory if processing
    progress = 0
    if job.status == "processing" and job_id in prediction_jobs:
        progress = prediction_jobs[job_id].get("progress", 0)
    elif job.status == "complete":
        progress = 100
        
    return PredictionJobInfo(
        job_id=job.job_id,
        filename=job.filename,
        status=job.status,
        progress=progress,
        result=result,
        error=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
        input_video_path=job.input_video_path,
        output_video_path=job.output_video_path
    )


@app.get("/api/predict-action/{job_id}/video")
async def get_prediction_video(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Stream annotated prediction video"""
    from app.db.models import Prediction
    
    job = db.query(Prediction).filter(Prediction.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != "complete":
        raise HTTPException(status_code=400, detail="Prediction not complete yet")
    
    output_video_path = job.output_video_path
    if not output_video_path:
        raise HTTPException(status_code=404, detail="Output video path not set")
    
    # Handle different video extensions from legacy jobs or format changes
    output_path = Path(output_video_path)
    
    # If explicit path doesn't exist, check for .webm (new format) or .avi (old format)
    if not output_path.exists():
        webm_path = output_path.with_suffix('.webm')
        avi_path = output_path.with_suffix('.avi')
        
        if webm_path.exists():
            output_path = webm_path
        elif avi_path.exists():
            output_path = avi_path
    
    # Debug logging
    print(f"[VIDEO] Requested video for job {job_id}")
    print(f"[VIDEO] Path from job: {output_video_path}")
    print(f"[VIDEO] Actual path: {output_path}")
    print(f"[VIDEO] Path exists: {output_path.exists()}")
    print(f"[VIDEO] File size: {output_path.stat().st_size if output_path.exists() else 'N/A'} bytes")
    
    if not output_path.exists():
        raise HTTPException(status_code=404, detail=f"Annotated video not found at {output_path}")
    
    # Determine media type based on extension
    if output_path.suffix == '.webm':
        media_type = "video/webm"
    elif output_path.suffix == '.avi':
        media_type = "video/x-msvideo"
    else:
        media_type = "video/mp4"
    
    # FileResponse automatically handles range requests for video streaming
    return FileResponse(
        path=str(output_path),
        media_type=media_type,
        filename=f"predicted_{Path(job.filename).stem}{output_path.suffix}"
    )


# ==================== Health Check ====================

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
