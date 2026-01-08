"""
Person Detection Service using YOLOv8
"""
import os
import numpy as np
from ultralytics import YOLO
from typing import List, Dict

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
