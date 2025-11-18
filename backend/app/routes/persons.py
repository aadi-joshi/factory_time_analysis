"""Person management endpoints: list persons, rename, merge, summary."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select
from typing import List
from ..database import get_session
from ..models import PersonTrack, TrackPoint, Video
from ..schemas import PersonSummary, PersonRename, MergePersonsRequest
import csv
from io import StringIO

router = APIRouter(prefix="/api/videos", tags=["persons"])

@router.get("/{video_id}/persons", response_model=List[PersonSummary])
def list_persons(video_id: int, session: Session = Depends(get_session)):
    video = session.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    persons = session.exec(select(PersonTrack).where(PersonTrack.video_id == video_id).where(PersonTrack.active == True)).all()
    summaries: List[PersonSummary] = []
    for p in persons:
        tps = session.exec(select(TrackPoint).where(TrackPoint.person_track_id == p.id)).all()
        total_frames = len(tps)
        va_frames = sum(1 for tp in tps if tp.value_added)
        frame_duration = 1 / video.fps if video.fps else 0
        total_time = total_frames * frame_duration
        va_time = va_frames * frame_duration
        nva_time = total_time - va_time
        ratio = va_time / total_time if total_time else 0
        summaries.append(PersonSummary(person_id=p.id, internal_track_id=p.internal_track_id, name=p.display_name, total_time_seconds=total_time, value_added_seconds=va_time, non_value_added_seconds=nva_time, value_added_ratio=ratio))
    return summaries

@router.patch("/{video_id}/persons/{person_id}", response_model=PersonSummary)
def rename_person(video_id: int, person_id: int, body: PersonRename, session: Session = Depends(get_session)):
    person = session.get(PersonTrack, person_id)
    if not person or person.video_id != video_id or not person.active:
        raise HTTPException(status_code=404, detail="Person not found")
    person.display_name = body.name
    session.add(person)
    session.commit()
    session.refresh(person)
    # compute summary
    video = session.get(Video, video_id)
    tps = session.exec(select(TrackPoint).where(TrackPoint.person_track_id == person.id)).all()
    total_frames = len(tps)
    va_frames = sum(1 for tp in tps if tp.value_added)
    frame_duration = 1 / video.fps if video.fps else 0
    total_time = total_frames * frame_duration
    va_time = va_frames * frame_duration
    nva_time = total_time - va_time
    ratio = va_time / total_time if total_time else 0
    return PersonSummary(person_id=person.id, internal_track_id=person.internal_track_id, name=person.display_name, total_time_seconds=total_time, value_added_seconds=va_time, non_value_added_seconds=nva_time, value_added_ratio=ratio)

@router.post("/{video_id}/merge-persons", response_model=List[PersonSummary])
def merge_persons(video_id: int, body: MergePersonsRequest, session: Session = Depends(get_session)):
    into = session.get(PersonTrack, body.into_id)
    from_person = session.get(PersonTrack, body.from_id)
    if not into or not from_person or into.video_id != video_id or from_person.video_id != video_id:
        raise HTTPException(status_code=404, detail="Persons not found")
    if into.id == from_person.id:
        raise HTTPException(status_code=400, detail="Cannot merge same person")
    # reassign trackpoints
    tps = session.exec(select(TrackPoint).where(TrackPoint.person_track_id == from_person.id)).all()
    for tp in tps:
        tp.person_track_id = into.id
        session.add(tp)
    from_person.active = False
    session.add(from_person)
    session.commit()
    # return updated summaries
    return list_persons(video_id, session)

@router.get("/{video_id}/summary", response_model=List[PersonSummary])
def summary(video_id: int, session: Session = Depends(get_session)):
    return list_persons(video_id, session)

@router.get("/{video_id}/export-summary")
def export_summary(video_id: int, session: Session = Depends(get_session)):
    persons = list_persons(video_id, session)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["person_id","internal_track_id","name","total_time_seconds","value_added_seconds","non_value_added_seconds","value_added_ratio"])
    for p in persons:
        writer.writerow([p.person_id, p.internal_track_id, p.name, f"{p.total_time_seconds:.4f}", f"{p.value_added_seconds:.4f}", f"{p.non_value_added_seconds:.4f}", f"{p.value_added_ratio:.4f}"])
    return Response(content=output.getvalue(), media_type="text/csv")

@router.get("/{video_id}/persons/{person_id}/thumbnail")
def person_thumbnail(video_id: int, person_id: int, session: Session = Depends(get_session)):
    person = session.get(PersonTrack, person_id)
    if not person or person.video_id != video_id or not person.active or not person.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    try:
        with open(person.thumbnail_path, 'rb') as f:
            data = f.read()
        return Response(content=data, media_type='image/jpeg')
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Thumbnail file missing")

@router.get("/{video_id}/analytics")
def analytics(video_id: int, session: Session = Depends(get_session)):
    persons = list_persons(video_id, session)
    total_va = sum(p.value_added_seconds for p in persons)
    total_nva = sum(p.non_value_added_seconds for p in persons)
    total = total_va + total_nva
    overall_ratio = (total_va/total) if total else 0
    return {
        "video_id": video_id,
        "overall": {"value_added_seconds": total_va, "non_value_added_seconds": total_nva, "value_added_ratio": overall_ratio},
        "persons": [p.dict() for p in persons]
    }
