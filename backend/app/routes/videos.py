"""Video related endpoints."""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlmodel import Session, select
import os
import shutil
import json
from ..config import settings
from ..database import get_session
from ..models import Video, Zone, PersonTrack, TrackPoint
from ..schemas import UploadVideoResponse, VideoListItem, VideoRead, ZoneCreate, ZoneRead, ProcessVideoResponse, FrameDataResponse, FrameTrackBBox, ZonePoint
from ..services.tracking import process_video
from ..utils.video_io import video_metadata, open_video, read_frame
from typing import List
from fastapi.responses import StreamingResponse, Response
import cv2

router = APIRouter(prefix="/api/videos", tags=["videos"])

os.makedirs(settings.video_storage_dir, exist_ok=True)

@router.post("/", response_model=UploadVideoResponse)
def upload_video(file: UploadFile = File(...), session: Session = Depends(get_session)):
    if not file.filename.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
        raise HTTPException(status_code=400, detail="Unsupported video format")
    stored_name = f"video_{file.filename.replace(' ', '_')}"
    dest_path = os.path.join(settings.video_storage_dir, stored_name)
    with open(dest_path, 'wb') as f:
        shutil.copyfileobj(file.file, f)
    fps, frame_count, duration_seconds = video_metadata(dest_path)
    video = Video(filename=stored_name, original_name=file.filename, fps=fps, frame_count=frame_count, duration_seconds=duration_seconds)
    session.add(video)
    session.commit()
    session.refresh(video)
    return video

@router.get("/", response_model=List[VideoListItem])
def list_videos(session: Session = Depends(get_session)):
    videos = session.exec(select(Video)).all()
    return videos

@router.get("/{video_id}", response_model=VideoRead)
def get_video(video_id: int, session: Session = Depends(get_session)):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@router.get("/{video_id}/first-frame")
def first_frame(video_id: int, session: Session = Depends(get_session)):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    path = os.path.join(settings.video_storage_dir, video.filename)
    cap = open_video(path)
    frame = read_frame(cap, 0)
    cap.release()
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not found")
    _, jpg = cv2.imencode('.jpg', frame)
    return Response(content=jpg.tobytes(), media_type='image/jpeg')

@router.post("/{video_id}/zones", response_model=List[ZoneRead])
def upsert_zones(video_id: int, zones: List[ZoneCreate], session: Session = Depends(get_session)):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    # remove existing zones
    existing = session.exec(select(Zone).where(Zone.video_id == video_id)).all()
    for z in existing:
        session.delete(z)
    session.commit()
    created: List[Zone] = []
    for z in zones:
        points_json = json.dumps([p.dict() for p in z.points])
        zone = Zone(video_id=video_id, name=z.name, points_json=points_json)
        session.add(zone)
        session.flush()
        created.append(zone)
    session.commit()
    # convert to ZoneRead
    out: List[ZoneRead] = []
    for z in created:
        pts = [ZonePoint(**p) for p in json.loads(z.points_json)]
        out.append(ZoneRead(id=z.id, name=z.name, points=pts))
    return out

@router.get("/{video_id}/zones", response_model=List[ZoneRead])
def get_zones(video_id: int, session: Session = Depends(get_session)):
    zones = session.exec(select(Zone).where(Zone.video_id == video_id)).all()
    out: List[ZoneRead] = []
    for z in zones:
        pts = [ZonePoint(**p) for p in json.loads(z.points_json)]
        out.append(ZoneRead(id=z.id, name=z.name, points=pts))
    return out

@router.post("/{video_id}/process", response_model=ProcessVideoResponse)
def process(video_id: int, session: Session = Depends(get_session)):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    zones_count = len(session.exec(select(Zone).where(Zone.video_id == video_id)).all())
    if zones_count == 0:
        raise HTTPException(status_code=400, detail="Define zones first")
    result = process_video(session, video_id)
    return ProcessVideoResponse(**result)

@router.get("/{video_id}/frame/{frame_index}")
def get_frame(video_id: int, frame_index: int, session: Session = Depends(get_session)):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if frame_index < 0 or frame_index >= video.frame_count:
        raise HTTPException(status_code=400, detail="Invalid frame index")
    path = os.path.join(settings.video_storage_dir, video.filename)
    cap = open_video(path)
    frame = read_frame(cap, frame_index)
    cap.release()
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not found")
    _, jpg = cv2.imencode('.jpg', frame)
    return Response(content=jpg.tobytes(), media_type='image/jpeg')

@router.get("/{video_id}/tracks/frame/{frame_index}", response_model=FrameDataResponse)
def frame_tracks(video_id: int, frame_index: int, session: Session = Depends(get_session)):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    tps = session.exec(select(TrackPoint, PersonTrack).join(PersonTrack).where(PersonTrack.video_id == video_id).where(TrackPoint.frame_index == frame_index).where(PersonTrack.active == True)).all()
    persons: List[FrameTrackBBox] = []
    for tp, person in tps:
        persons.append(FrameTrackBBox(
            person_id=person.id,
            display_name=person.display_name,
            internal_track_id=person.internal_track_id,
            frame_index=tp.frame_index,
            value_added=tp.value_added,
            bbox=[tp.bbox_x, tp.bbox_y, tp.bbox_w, tp.bbox_h]
        ))
    # zones
    zones = session.exec(select(Zone).where(Zone.video_id == video_id)).all()
    zone_reads: List[ZoneRead] = []
    import json as _json
    for z in zones:
        pts = [ZonePoint(**p) for p in _json.loads(z.points_json)]
        zone_reads.append(ZoneRead(id=z.id, name=z.name, points=pts))
    return FrameDataResponse(frame_index=frame_index, persons=persons, zones=zone_reads)
