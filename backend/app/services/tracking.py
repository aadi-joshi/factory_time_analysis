"""Video processing and tracking pipeline using YOLOv8 with improved ID consistency,
zone overlap calculation, and thumbnail + appearance feature extraction for merging fragmented tracks."""
from typing import List, Dict, Any, Tuple
from sqlmodel import Session, select
from ultralytics import YOLO  # type: ignore
try:
    # Torch 2.6+ defaults weights_only=True for torch.load. Allowlist Ultralytics classes.
    from torch.serialization import add_safe_globals  # type: ignore
    from ultralytics.nn.tasks import DetectionModel  # type: ignore
    add_safe_globals([DetectionModel])
except Exception:
    # If this import fails (older Torch), it's safe to continue.
    pass

# Torch 2.6+ compatibility: ensure torch.load defaults to weights_only=False for older checkpoints
try:
    import torch  # type: ignore
    _orig_torch_load = torch.load
    def _torch_load_compat(*args, **kwargs):
        if 'weights_only' not in kwargs:
            kwargs['weights_only'] = False
        return _orig_torch_load(*args, **kwargs)
    torch.load = _torch_load_compat  # type: ignore
except Exception:
    pass
import cv2
import json
from ..config import settings
from ..models import Video, Zone, PersonTrack, TrackPoint
from .geometry import point_in_polygon
import os
import sys
import math
try:
    from shapely.errors import GEOSException  # type: ignore
except Exception:
    class GEOSException(Exception):
        pass
try:
    from shapely.validation import make_valid  # type: ignore
except Exception:
    make_valid = None  # type: ignore

try:
    from shapely.geometry import Polygon, box as shapely_box  # type: ignore
except Exception:
    Polygon = None  # type: ignore


_model_cache: YOLO | None = None

def get_model() -> YOLO:
    global _model_cache
    if _model_cache is None:
        _model_cache = YOLO("yolov8n.pt")  # lightweight
    return _model_cache


def _compute_hist(bgr_img) -> List[float]:
    """Compute a simple normalized HSV histogram flattened."""
    hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv],[0,1,2], None, [8,8,8],[0,180,0,256,0,256])
    cv2.normalize(hist, hist)
    return hist.flatten().astype(float).tolist()

def _hist_similarity(h1: List[float], h2: List[float]) -> float:
    import numpy as np
    a = np.array(h1, dtype=float)
    b = np.array(h2, dtype=float)
    # correlation
    if a.size != b.size or a.size == 0:
        return 0.0
    a_mean = a.mean(); b_mean = b.mean()
    num = ((a - a_mean)*(b - b_mean)).sum()
    den = math.sqrt(((a - a_mean)**2).sum() * ((b - b_mean)**2).sum())
    return float(num/den) if den else 0.0

def _bbox_iou(a: Tuple[float,float,float,float], b: Tuple[float,float,float,float]) -> float:
    ax1, ay1, aw, ah = a; bx1, by1, bw, bh = b
    ax2 = ax1 + aw; ay2 = ay1 + ah; bx2 = bx1 + bw; by2 = by1 + bh
    inter_x1 = max(ax1, bx1); inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2); inter_y2 = min(ay2, by2)
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0
    inter_area = (inter_x2 - inter_x1)*(inter_y2 - inter_y1)
    a_area = aw*ah; b_area = bw*bh
    return inter_area / (a_area + b_area - inter_area)

def _clean_geometry(g):
    """Attempt to repair invalid geometry using buffer(0) or make_valid."""
    try:
        if not g.is_valid:
            # First attempt: classic buffer(0) fix
            g = g.buffer(0)
        if not g.is_valid and make_valid:
            g = make_valid(g)
    except Exception:
        pass
    return g

def _approx_overlap(bbox: Tuple[float,float,float,float], zone_poly: List[Tuple[float,float]]) -> float:
    """Approximate overlap by sampling a 12x12 grid inside bbox and counting points in polygon."""
    x,y,w,h = bbox
    if w <= 0 or h <= 0:
        return 0.0
    samples = 0
    inside = 0
    steps = 12
    for ix in range(steps):
        for iy in range(steps):
            sx = x + (ix + 0.5) * w / steps
            sy = y + (iy + 0.5) * h / steps
            samples += 1
            if point_in_polygon((sx, sy), zone_poly):
                inside += 1
    return inside / samples if samples else 0.0

def _zone_overlap(bbox: Tuple[float,float,float,float], zone_poly: List[Tuple[float,float]]) -> float:
    """Return fraction of bbox area overlapped by zone polygon.
    Robust to invalid polygons: tries Shapely precise area; falls back to sampling.
    """
    x,y,w,h = bbox
    bbox_area = w*h if w>0 and h>0 else 0.0
    if bbox_area <= 0:
        return 0.0
    if not Polygon:
        return _approx_overlap(bbox, zone_poly)
    try:
        poly = Polygon(zone_poly)
    except Exception:
        return _approx_overlap(bbox, zone_poly)
    poly = _clean_geometry(poly)
    try:
        bb = shapely_box(x, y, x+w, y+h)
        bb = _clean_geometry(bb)
        inter = bb.intersection(poly)
        if inter.is_empty:
            return 0.0
        inter_area = inter.area
        if inter_area < 0:  # guard improbable negative due to precision
            return 0.0
        return float(inter_area / bbox_area)
    except GEOSException:  # topology error -> fallback
        return _approx_overlap(bbox, zone_poly)
    except Exception:
        return _approx_overlap(bbox, zone_poly)

def process_video(session: Session, video_id: int) -> Dict[str, Any]:
    video = session.get(Video, video_id)
    if not video:
        raise ValueError("Video not found")
    zones = session.exec(select(Zone).where(Zone.video_id == video_id)).all()
    zone_polys: List[tuple[int, List[tuple[float, float]]]] = []
    for z in zones:
        pts = [(p['x'], p['y']) for p in json.loads(z.points_json)]
        zone_polys.append((z.id, pts))

    # Ensure 'lap' import is available for Ultralytics tracker (uses lap package name)
    try:
        import lap  # type: ignore
    except Exception:
        try:
            import lapx as _lap  # type: ignore
            sys.modules['lap'] = _lap
        except Exception:
            pass

    model = get_model()
    video_path = os.path.join(settings.video_storage_dir, video.filename)
    # choose tracker type (requires relevant tracker yaml bundled with ultralytics)
    tracker_cfg = None
    if settings.tracker_type:
        # ultralytics expects path or name ending with .yaml
        if settings.tracker_type.lower() == "bytetrack":
            tracker_cfg = "bytetrack.yaml"
        elif settings.tracker_type.lower() == "strongsort":
            tracker_cfg = "strongsort.yaml"
        elif settings.tracker_type.lower() == "deepsort":
            tracker_cfg = "deepsort.yaml"

    results_stream = model.track(
        source=video_path,
        stream=True,
        classes=[0],
        persist=True,
        conf=settings.detection_conf,
        iou=settings.iou,
        tracker=tracker_cfg
    )

    track_map: Dict[int, PersonTrack] = {}
    # Appearance feature store keyed by canonical person_track_id
    appearance_features: Dict[int, List[float]] = {}
    # Mapping from raw tracker id to canonical person_track_id
    id_mapping: Dict[int, int] = {}
    processed_frames = 0

    stride = max(1, settings.process_frame_stride)
    frame_index_counter = -1

    for result in results_stream:
        frame_index_counter += 1
        frame_index = frame_index_counter
        if frame_index % stride != 0:
            continue
        processed_frames += 1
        boxes = result.boxes
        if boxes is None:
            continue
        ids = boxes.id
        if ids is None:
            continue
        for i, box in enumerate(boxes.xywh.tolist()):  # center x,y,w,h
            raw_track_id = int(ids[i])
            # YOLO xywh are center x,y,w,h; convert to top-left
            cx, cy, w, h = box
            x = cx - w / 2
            y = cy - h / 2
            centroid_x = cx
            centroid_y = cy
            # Determine canonical track id via appearance + IoU merging
            canonical_id = id_mapping.get(raw_track_id)
            crop_img = None
            if hasattr(result, 'orig_img') and result.orig_img is not None:
                frame_img = result.orig_img
                # crop safely
                ih, iw = frame_img.shape[:2]
                rx1 = max(int(x),0); ry1 = max(int(y),0); rx2 = min(int(x+w), iw); ry2 = min(int(y+h), ih)
                if rx2>rx1 and ry2>ry1:
                    crop_img = frame_img[ry1:ry2, rx1:rx2]
            hist = _compute_hist(crop_img) if crop_img is not None else []

            if canonical_id is None and hist:
                # try to match existing appearance feature
                best_id = None
                best_score = 0.0
                for existing_id, feat in appearance_features.items():
                    score = _hist_similarity(hist, feat)
                    if score > best_score:
                        best_score = score
                        best_id = existing_id
                if best_id is not None and best_score >= settings.merge_hist_threshold:
                    # also require IoU with last bbox of that person above threshold (optional)
                    last_tp = session.exec(select(TrackPoint).where(TrackPoint.person_track_id == best_id).order_by(TrackPoint.frame_index.desc()).limit(1)).first()
                    if last_tp:
                        iou_val = _bbox_iou((x,y,w,h),(last_tp.bbox_x,last_tp.bbox_y,last_tp.bbox_w,last_tp.bbox_h))
                        if iou_val >= settings.merge_iou_threshold:
                            canonical_id = best_id

            if canonical_id is None:
                # create new person track
                pt = PersonTrack(video_id=video_id, internal_track_id=raw_track_id, display_name=f"Worker #{len(track_map)+1}")
                if crop_img is not None:
                    os.makedirs(settings.thumbnail_dir, exist_ok=True)
                    thumb_path = os.path.join(settings.thumbnail_dir, f"video{video_id}_person_{len(track_map)+1}.jpg")
                    cv2.imwrite(thumb_path, crop_img)
                    pt.thumbnail_path = thumb_path
                if hist:
                    pt.feature_json = json.dumps(hist)
                    appearance_features_raw = hist
                else:
                    appearance_features_raw = []
                session.add(pt)
                session.flush()
                track_map[pt.id] = pt
                canonical_id = pt.id
                if appearance_features_raw:
                    appearance_features[canonical_id] = appearance_features_raw
                id_mapping[raw_track_id] = canonical_id
            else:
                # existing track
                person_track = session.get(PersonTrack, canonical_id)
                if person_track and hist:
                    # update running feature (simple moving average)
                    import numpy as np
                    old = appearance_features.get(canonical_id)
                    new_arr = np.array(hist)
                    if old:
                        old_arr = np.array(old)
                        merged = (old_arr*0.7 + new_arr*0.3).tolist()
                    else:
                        merged = new_arr.tolist()
                    appearance_features[canonical_id] = merged
                    person_track.feature_json = json.dumps(merged)
                    session.add(person_track)
                id_mapping[raw_track_id] = canonical_id
                pt = person_track
            person_track = session.get(PersonTrack, canonical_id)

            # zone overlap computation
            value_added = False
            zone_id_hit = None
            bbox_tuple = (x,y,w,h)
            for zid, poly in zone_polys:
                overlap_fraction = _zone_overlap(bbox_tuple, poly)
                if overlap_fraction >= settings.zone_overlap_threshold:
                    value_added = True
                    zone_id_hit = zid
                    break
            # fallback centroid if no overlap triggered (legacy behavior)
            if not value_added:
                for zid, poly in zone_polys:
                    if point_in_polygon((centroid_x, centroid_y), poly):
                        value_added = True
                        zone_id_hit = zid
                        break
            tp = TrackPoint(
                person_track_id=person_track.id,
                frame_index=frame_index,
                timestamp=frame_index / video.fps,
                bbox_x=x,
                bbox_y=y,
                bbox_w=w,
                bbox_h=h,
                centroid_x=centroid_x,
                centroid_y=centroid_y,
                value_added=value_added,
                zone_id=zone_id_hit
            )
            session.add(tp)
        session.commit()
    persons_result = session.exec(
        select(PersonTrack).where(
            PersonTrack.video_id == video_id,
            PersonTrack.active == True,
        )
    )
    persons_detected = len(list(persons_result))
    return {"status": "completed", "processed_frames": processed_frames, "persons_detected": persons_detected}
