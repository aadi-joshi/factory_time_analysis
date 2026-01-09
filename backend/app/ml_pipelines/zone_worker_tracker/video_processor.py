"""
Video Processing Service
Orchestrates detection and tracking pipeline for video analysis
"""
import cv2
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Set

from .detection import DetectionService
from .tracking import TrackingService


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
