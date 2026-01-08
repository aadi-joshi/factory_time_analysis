"""
Geometry utilities for zone-based analysis
"""
import json
from typing import List, Tuple, Dict
from shapely.geometry import Polygon, Point
import numpy as np


class ZoneGeometry:
    """Utilities for zone polygon operations"""
    
    @staticmethod
    def create_polygon(coordinates: List[Tuple[float, float]]) -> Polygon:
        """Create Shapely polygon from list of (x, y) coordinates"""
        return Polygon(coordinates)
    
    @staticmethod
    def point_in_polygon(point: Tuple[float, float], polygon: Polygon) -> bool:
        """Check if point is inside polygon"""
        return polygon.contains(Point(point[0], point[1]))
    
    @staticmethod
    def point_in_polygon_coords(point_x: float, point_y: float, coords: List[List[float]]) -> bool:
        """Check if point is inside polygon defined by coordinates"""
        poly = Polygon(coords)
        return poly.contains(Point(point_x, point_y))
    
    @staticmethod
    def polygon_from_json(json_str: str) -> Polygon:
        """Load polygon from JSON string"""
        coords = json.loads(json_str)
        return Polygon(coords)
    
    @staticmethod
    def polygon_to_json(polygon: Polygon) -> str:
        """Convert polygon to JSON string"""
        coords = list(polygon.exterior.coords)[:-1]  # Remove duplicate last point
        return json.dumps(coords)


class VANVACalculator:
    """Calculate VA/NVA time metrics"""
    
    @staticmethod
    def calculate_metrics(
        tracks_per_frame: List[Dict],  # List of {frame_idx, tracks: [...]}
        worker_va_zones: Dict[str, List[str]],  # worker_id -> list of zone_ids
        video_fps: float,
        zone_data: Dict[str, Dict]  # zone_id -> {polygon_json, ...}
    ) -> Dict:
        """
        Calculate VA/NVA metrics for all workers
        
        Args:
            tracks_per_frame: tracking data per frame
            worker_va_zones: mapping of worker_id to their VA zone_ids
            video_fps: frames per second
            zone_data: zone geometry data (zone_id -> {polygon_json, ...})
        
        Returns: dict of worker_id -> {va_frames, nva_frames, va_seconds, nva_seconds, va_percentage}
        """
        metrics = {}
        
        # Initialize counters for all workers
        for worker_id in worker_va_zones.keys():
            metrics[worker_id] = {
                "va_frames": 0,
                "nva_frames": 0,
                "total_frames": 0
            }
        
        # Process each frame
        for frame_data in tracks_per_frame:
            for track in frame_data.get("tracks", []):
                worker_id = str(track["track_id"])
                
                if worker_id not in metrics:
                    continue
                
                centroid_x, centroid_y = track["centroid"]
                va_zone_ids = worker_va_zones.get(worker_id, [])
                
                # Check if centroid is in any VA zone
                in_va_zone = False
                for zone_id in va_zone_ids:
                    if zone_id in zone_data:
                        zone_info = zone_data[zone_id]
                        polygon = ZoneGeometry.polygon_from_json(zone_info["polygon_json"])
                        if ZoneGeometry.point_in_polygon((centroid_x, centroid_y), polygon):
                            in_va_zone = True
                            break
                
                if in_va_zone:
                    metrics[worker_id]["va_frames"] += 1
                else:
                    metrics[worker_id]["nva_frames"] += 1
                
                metrics[worker_id]["total_frames"] += 1
        
        # Convert frames to seconds and calculate percentages
        for worker_id in metrics:
            total_frames = metrics[worker_id]["total_frames"]
            va_frames = metrics[worker_id]["va_frames"]
            nva_frames = metrics[worker_id]["nva_frames"]
            
            metrics[worker_id]["va_seconds"] = va_frames / video_fps if video_fps > 0 else 0
            metrics[worker_id]["nva_seconds"] = nva_frames / video_fps if video_fps > 0 else 0
            
            if total_frames > 0:
                metrics[worker_id]["va_percentage"] = (va_frames / total_frames) * 100
            else:
                metrics[worker_id]["va_percentage"] = 0
            
            # Remove temporary counters
            del metrics[worker_id]["total_frames"]
        
        return metrics
    
    @staticmethod
    def calculate_metrics_for_merged_ids(
        all_metrics: Dict,  # worker_id -> metrics
        id_merges: List[Dict],  # {merged_worker_id, original_track_ids}
    ) -> Dict:
        """
        Recompute metrics after ID merging
        
        Args:
            all_metrics: original metrics per worker
            id_merges: list of merge operations
        
        Returns: merged metrics dict
        """
        merged_metrics = dict(all_metrics)
        
        for merge in id_merges:
            merged_id = merge["merged_worker_id"]
            original_ids = merge["original_track_ids"]
            
            va_frames = 0
            nva_frames = 0
            
            for orig_id in original_ids:
                orig_id_str = str(orig_id)
                if orig_id_str in all_metrics:
                    va_frames += all_metrics[orig_id_str].get("va_frames", 0)
                    nva_frames += all_metrics[orig_id_str].get("nva_frames", 0)
            
            total_frames = va_frames + nva_frames
            merged_metrics[merged_id] = {
                "va_frames": va_frames,
                "nva_frames": nva_frames,
                "va_seconds": va_frames / all_metrics.get(str(original_ids[0]), {}).get("video_fps", 30),
                "nva_seconds": nva_frames / all_metrics.get(str(original_ids[0]), {}).get("video_fps", 30),
                "va_percentage": (va_frames / total_frames * 100) if total_frames > 0 else 0
            }
            
            # Remove original IDs
            for orig_id in original_ids:
                merged_metrics.pop(str(orig_id), None)
        
        return merged_metrics
