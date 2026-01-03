"""
SORT (Simple Online and Realtime Tracking) implementation
Based on: https://github.com/abewley/sort
"""

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import euclidean
from filterpy.kalman import KalmanFilter


class KalmanBoxTracker:
    """
    This class represents the internal state of individual tracked objects as centroid location and speed.
    """
    count = 0
    
    def __init__(self, bbox):
        """
        Initialize Kalman filter for bounding box
        bbox: [x1, y1, x2, y2] format
        """
        # Define constant velocity motion model
        self.kf = KalmanFilter(dim_x=7, dim_z=4)
        self.kf.F = np.array([
            [1, 0, 0, 0, 1, 0, 0],
            [0, 1, 0, 0, 0, 1, 0],
            [0, 0, 1, 0, 0, 0, 1],
            [0, 0, 0, 1, 0, 0, 0],
            [0, 0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 1]
        ])
        
        self.kf.H = np.array([
            [1, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0]
        ])
        
        self.kf.R[2:, 2:] *= 10.
        self.kf.P[4:, 4:] *= 1000.
        self.kf.P *= 10.
        self.kf.Q[-1, -1] *= 0.01
        self.kf.Q[4:, 4:] *= 0.01
        
        self.kf.x[:4] = self.convert_bbox_to_z(bbox)
        self.time_since_update = 0
        self.id = KalmanBoxTracker.count
        KalmanBoxTracker.count += 1
        self.history = []
        self.hits = 0
        self.hit_streak = 0
        self.age = 0
    
    def update(self, bbox):
        """Update state vector with observed bbox"""
        self.time_since_update = 0
        self.history = []
        self.hits += 1
        self.hit_streak += 1
        self.kf.update(self.convert_bbox_to_z(bbox))
    
    def predict(self):
        """Advance state space by one time step"""
        if (self.kf.x[6] + self.kf.x[2]) <= 0:
            self.kf.x[6] *= 0.0
        self.kf.predict()
        self.age += 1
        if self.time_since_update > 0:
            self.hit_streak = 0
        self.time_since_update += 1
        self.history.append(self.convert_x_to_bbox(self.kf.x))
        return self.history[-1]
    
    def get_state(self):
        """Return bbox from state vector"""
        return self.convert_x_to_bbox(self.kf.x)
    
    @staticmethod
    def convert_bbox_to_z(bbox):
        """Convert bounding box [x1, y1, x2, y2] to [cx, cy, area, ratio]"""
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = bbox[0] + w / 2.
        y = bbox[1] + h / 2.
        s = w * h
        r = w / float(h)
        return np.array([x, y, s, r]).reshape((4, 1))
    
    @staticmethod
    def convert_x_to_bbox(x, score=None):
        """Convert state [cx, cy, area, ratio] to bbox [x1, y1, x2, y2]"""
        w = np.sqrt(x[2] * x[3])
        h = x[2] / w
        if score is None:
            return np.array([x[0] - w / 2., x[1] - h / 2., x[0] + w / 2., x[1] + h / 2.]).reshape((1, 4))[0]
        else:
            return np.array([x[0] - w / 2., x[1] - h / 2., x[0] + w / 2., x[1] + h / 2., score]).reshape((1, 5))[0]


class SORT:
    """
    SORT: Simple, Online and Realtime Tracking
    """
    
    def __init__(self, max_age=30, min_hits=3, iou_threshold=0.3):
        """
        Initialize SORT
        max_age: maximum frames to keep track alive without detection
        min_hits: minimum detections before track is output
        iou_threshold: IoU threshold for matching
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.trackers = []
        self.frame_count = 0
    
    def update(self, dets=np.empty((0, 5))):
        """
        Updates the tracker with observations.
        dets: array of detections [x1, y1, x2, y2, confidence]
        Returns: array of tracks [x1, y1, x2, y2, track_id]
        """
        self.frame_count += 1
        
        # Get predictions
        trks = np.zeros((len(self.trackers), 5))
        to_del = []
        ret = []
        
        for i, trk in enumerate(trks):
            # predict() already returns a 1D bbox array [x1, y1, x2, y2]
            pos = self.trackers[i].predict()
            trk[:] = [pos[0], pos[1], pos[2], pos[3], 0]
            if np.any(np.isnan(pos)):
                to_del.append(i)
        
        trks = np.ma.compress_rows(np.ma.masked_invalid(trks))
        for i in reversed(to_del):
            self.trackers.pop(i)
        
        matched, unmatched_dets, unmatched_trks = self._associate_detections_to_trackers(
            dets, trks, self.iou_threshold
        )
        
        # Update matched trackers
        for m in matched:
            self.trackers[m[1]].update(dets[m[0], :4])
        
        # Create and initialize new trackers
        for i in unmatched_dets:
            trk = KalmanBoxTracker(dets[i, :4])
            self.trackers.append(trk)
        
        # Return output
        for i, trk in enumerate(self.trackers):
            # get_state() returns a 1D bbox array [x1, y1, x2, y2]
            d = trk.get_state()
            if (trk.time_since_update < 1) and (trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits):
                ret.append(np.concatenate((d, [trk.id + 1])).reshape(1, -1))
        
        if len(ret) > 0:
            return np.concatenate(ret)
        return np.empty((0, 5))
    
    @staticmethod
    def _iou(bbox1, bbox2):
        """Compute Intersection over Union"""
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2
        
        intersect_xmin = max(x1_min, x2_min)
        intersect_ymin = max(y1_min, y2_min)
        intersect_xmax = min(x1_max, x2_max)
        intersect_ymax = min(y1_max, y2_max)
        
        if intersect_xmax < intersect_xmin or intersect_ymax < intersect_ymin:
            return 0.0
        
        intersect_area = (intersect_xmax - intersect_xmin) * (intersect_ymax - intersect_ymin)
        bbox1_area = (x1_max - x1_min) * (y1_max - y1_min)
        bbox2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = bbox1_area + bbox2_area - intersect_area
        
        return intersect_area / union_area if union_area > 0 else 0.0
    
    @staticmethod
    def _associate_detections_to_trackers(detections, trackers, iou_threshold=0.3):
        """
        Associate detections to tracked objects using IoU
        Returns: matched, unmatched_detections, unmatched_trackers
        """
        if len(trackers) == 0:
            return np.empty((0, 2), dtype=int), np.arange(len(detections)), np.empty((0,), dtype=int)
        
        if len(detections) == 0:
            return np.empty((0, 2), dtype=int), np.empty((0,), dtype=int), np.arange(len(trackers))
        
        # Build IoU matrix
        iou_matrix = np.zeros((len(detections), len(trackers)))
        for d, det in enumerate(detections):
            for t, trk in enumerate(trackers):
                iou_matrix[d, t] = SORT._iou(det[:4], trk[:4])
        
        # Hungarian algorithm
        matched_indices = linear_sum_assignment(-iou_matrix)
        matched_indices = np.column_stack(matched_indices)
        
        unmatched_detections = []
        for d, det in enumerate(detections):
            if d not in matched_indices[:, 0]:
                unmatched_detections.append(d)
        
        unmatched_trackers = []
        for t, trk in enumerate(trackers):
            if t not in matched_indices[:, 1]:
                unmatched_trackers.append(t)
        
        # Filter by IoU threshold
        matches = []
        for m in matched_indices:
            if iou_matrix[m[0], m[1]] < iou_threshold:
                unmatched_detections.append(m[0])
                unmatched_trackers.append(m[1])
            else:
                matches.append(m)
        
        if len(matches) == 0:
            matches = np.empty((0, 2), dtype=int)
        else:
            matches = np.array(matches)
        
        return matches, np.array(unmatched_detections), np.array(unmatched_trackers)


# Install: pip install filterpy
