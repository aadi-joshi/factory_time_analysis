from sqlmodel import Session
from backend.app.database import engine, init_db
from backend.app.models import Video, PersonTrack, TrackPoint

def setup_module():
    init_db()

def test_summary_math_basic():
    # create video
    with Session(engine) as session:
        vid = Video(filename='dummy.mp4', original_name='dummy.mp4', fps=10.0, frame_count=100, duration_seconds=10.0)
        session.add(vid)
        session.commit(); session.refresh(vid)
        person = PersonTrack(video_id=vid.id, internal_track_id=1, display_name='Worker #1')
        session.add(person); session.commit(); session.refresh(person)
        # 10 frames VA, 10 frames NVA
        for i in range(20):
            tp = TrackPoint(person_track_id=person.id, frame_index=i, timestamp=i/vid.fps, bbox_x=0,bbox_y=0,bbox_w=10,bbox_h=10, centroid_x=5, centroid_y=5, value_added=(i<10), zone_id=None)
            session.add(tp)
        session.commit()
        # compute
        tps = person.points
        total_frames = len(tps)
        va_frames = sum(1 for tp in tps if tp.value_added)
        assert total_frames == 20
        assert va_frames == 10
        frame_duration = 1/vid.fps
        total_time = total_frames * frame_duration
        va_time = va_frames * frame_duration
        assert total_time == 2.0
        assert va_time == 1.0
