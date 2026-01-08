"""
Multi-Object Tracking Service using SORT
"""
import numpy as np
from typing import List, Dict
from .sort import SORT


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
