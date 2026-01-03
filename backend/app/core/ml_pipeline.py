"""
Detection and Tracking services
"""
import os
import cv2
import numpy as np
from ultralytics import YOLO
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Set
from app.core.sort import SORT

# Disable PyTorch weights_only for compatibility with older YOLO models
os.environ['TORCH_WEIGHTS_ONLY'] = 'False'


class DetectionService:
    """YOLOv8n detection service"""
    
    def __init__(self, model_path: str = "yolov8n.pt", device: str = "cpu"):
        """
        Initialize YOLOv8n detector
        model_path: path to model weights (auto-downloads if needed)
        device: 'cpu' or 'cuda'
        """
        self.model = YOLO(model_path)
        self.device = device
        self.model.to(device)
    
    def detect_persons(self, frame: np.ndarray, confidence_threshold: float = 0.5) -> List[Dict]:
        """
        Detect persons in frame
        Returns: list of dicts with keys: bbox, confidence
        """
        results = self.model(frame, verbose=False, device=self.device, imgsz=640)
        
        detections = []
        for result in results:
            for box in result.boxes:
                cls = int(box.cls)
                if cls == 0:  # class 0 = person
                    conf = float(box.conf)
                    if conf >= confidence_threshold:
                        bbox = box.xyxy[0].cpu().numpy().astype(np.float32)
                        detections.append({
                            "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
                            "confidence": conf
                        })
        
        return detections


class TrackingService:
    """Multi-object tracking service using SORT"""
    
    def __init__(self, max_age: int = 30, min_hits: int = 3):
        """Initialize SORT tracker"""
        self.tracker = SORT(max_age=max_age, min_hits=min_hits)
    
    def update(self, detections: List[Dict]) -> List[Dict]:
        """
        Update tracker with detections
        detections: list of {bbox: [x1, y1, x2, y2], confidence: float}
        Returns: list of {bbox: [x1, y1, x2, y2], track_id: int, centroid: [x, y], confidence: float}
        """
        # Convert to format for SORT: [[x1, y1, x2, y2, conf], ...]
        if len(detections) > 0:
            dets = np.array([
                [d["bbox"][0], d["bbox"][1], d["bbox"][2], d["bbox"][3], d["confidence"]]
                for d in detections
            ])
        else:
            dets = np.empty((0, 5))
        
        # Update SORT
        tracks = self.tracker.update(dets)
        
        # Format output
        result = []
        for track in tracks:
            x1, y1, x2, y2, track_id = track
            centroid_x = (x1 + x2) / 2.0
            centroid_y = (y1 + y2) / 2.0
            
            result.append({
                "bbox": [float(x1), float(y1), float(x2), float(y2)],
                "track_id": int(track_id),
                "centroid": [float(centroid_x), float(centroid_y)],
                "confidence": 0.95  # SORT doesn't output confidence, so use high default
            })
        
        return result


class VideoProcessingService:
    """Service for video processing pipeline"""
    
    def __init__(self, detector: DetectionService):
        self.detector = detector
        self.tracker = TrackingService()
    
    def process_video(
        self,
        video_path: str,
        callback=None,
        portraits_dir: Optional[str] = None,
    ) -> Tuple[List, Dict]:
        """
        Process entire video with detection and tracking
        callback: optional function(frame_idx, total_frames) for progress
        Returns: (all_tracks, video_metadata)
        """
        cap = cv2.VideoCapture(video_path)
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_sec = total_frames / fps if fps > 0 else 0
        
        metadata = {
            "fps": fps,
            "width": width,
            "height": height,
            "total_frames": total_frames,
            "duration_sec": duration_sec
        }
        
        all_tracks = []
        frame_idx = 0

        portraits_path: Optional[Path] = None
        saved_portraits: Set[int] = set()
        if portraits_dir:
            portraits_path = Path(portraits_dir)
            portraits_path.mkdir(parents=True, exist_ok=True)
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if callback:
                callback(frame_idx, total_frames)
            
            # Detect persons
            detections = self.detector.detect_persons(frame, confidence_threshold=0.5)
            
            # Track
            tracks = self.tracker.update(detections)

            # Optionally save a representative crop for each worker ID
            if portraits_path is not None and len(tracks) > 0:
                for track in tracks:
                    worker_id = int(track["track_id"])
                    if worker_id in saved_portraits:
                        continue

                    x1, y1, x2, y2 = [int(v) for v in track["bbox"]]

                    # Clamp coordinates to frame bounds
                    x1 = max(0, min(x1, width - 1))
                    y1 = max(0, min(y1, height - 1))
                    x2 = max(0, min(x2, width))
                    y2 = max(0, min(y2, height))

                    if x2 <= x1 or y2 <= y1:
                        continue

                    crop = frame[y1:y2, x1:x2]
                    if crop.size == 0:
                        continue

                    out_path = portraits_path / f"{worker_id}.jpg"
                    try:
                        cv2.imwrite(str(out_path), crop)
                        saved_portraits.add(worker_id)
                    except Exception:
                        # Fail silently for portrait saving; core tracking must continue
                        pass
            
            # Store frame tracks
            frame_data = {
                "frame_idx": frame_idx,
                "tracks": tracks
            }
            all_tracks.append(frame_data)
            
            frame_idx += 1
        
        cap.release()
        return all_tracks, metadata
    
    def extract_first_frame(self, video_path: str, output_path: str) -> bool:
        """Extract and save first frame"""
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            cv2.imwrite(output_path, frame)
            return True
        return False
