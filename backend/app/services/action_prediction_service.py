"""
Action Prediction Service
Wrapper for two-stage temporal action recognition ML models
"""
import os
import json
import cv2
import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional

# Import from Predicition module
import sys
sys.path.append(str(Path(__file__).parent.parent / "Predicition"))

from train_deployment_model import (
    build_r3d18_feature_extractor,
    extract_features_steps_r3d18,
    TemporalClassifier,
    TARGET_FPS, CLIP_LEN, FEATURE_DIM, FIXED_T
)

# Model paths - using ML Models directory
ML_MODELS_DIR = Path(__file__).parent.parent.parent.parent / "ML Models"
STAGE1_DIR = ML_MODELS_DIR / "stage1"
STAGE2_DIR = ML_MODELS_DIR / "stage2"

# Video overlay parameters
OVERLAY_COLORS = {
    "VA": (0, 255, 0),          # Bright Green
    "RNVA": (0, 140, 255),      # Bright Orange (BGR format)
    "NVA": (0, 0, 255),         # Bright Red
    "UNKNOWN": (128, 128, 128)  # Gray
}

FONT_SCALE = 0.8
FONT_THICKNESS = 3
BACKGROUND_ALPHA = 0.7
TEXT_ALPHA = 0.3


class ActionPredictionService:
    """Service for predicting actions from factory videos"""
    
    def __init__(self, device: str = None):
        """Initialize the prediction service
        
        Args:
            device: 'cuda' or 'cpu'. If None, auto-detect.
        """
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        
        print(f"🔧 ActionPredictionService initializing on device: {self.device}")
        
        # Load R3D-18 backbone
        print("🧠 Loading R3D-18 feature extractor...")
        self.backbone, self.r3d_mean, self.r3d_std = build_r3d18_feature_extractor(self.device)
        print("   ✅ R3D-18 ready")
        
        # Load Stage-1 model
        print("📦 Loading Stage-1 model...")
        self.stage1_l2i = self._load_label_map(STAGE1_DIR / "label_map.json")
        self.stage1_i2l = {v: k for k, v in self.stage1_l2i.items()}
        self.stage1_model = TemporalClassifier(
            in_dim=FEATURE_DIM, 
            num_classes=len(self.stage1_l2i), 
            hidden=256
        ).to(self.device)
        self.stage1_model.load_state_dict(
            torch.load(STAGE1_DIR / "best.pt", map_location=self.device, weights_only=False)
        )
        self.stage1_model.eval()
        print(f"   ✅ Stage-1 loaded | Classes: {len(self.stage1_l2i)}")
        
        # Load Stage-2 models
        print("📦 Loading Stage-2 models...")
        self.stage2_registry = self._load_stage2_registry()
        self.stage2_models = {}
        self.stage2_label_maps = {}
        
        for family, info in self.stage2_registry.items():
            if info.get("trained"):
                family_dir = STAGE2_DIR / family
                label_map = self._load_label_map(family_dir / "label_map.json")
                model = TemporalClassifier(
                    in_dim=FEATURE_DIM, 
                    num_classes=len(label_map), 
                    hidden=256
                ).to(self.device)
                model.load_state_dict(
                    torch.load(family_dir / "best.pt", map_location=self.device, weights_only=False)
                )
                model.eval()
                self.stage2_models[family] = model
                self.stage2_label_maps[family] = label_map
                print(f"   ✅ {family}: {len(label_map)} classes")
        
        print(f"   Total Stage-2 models loaded: {len(self.stage2_models)}")
        print("✅ ActionPredictionService ready")
    
    def _load_label_map(self, path: Path) -> Dict:
        """Load label map from JSON"""
        with open(path, "r") as f:
            return json.load(f)
    
    def _load_stage2_registry(self) -> Dict:
        """Load Stage-2 model registry"""
        registry_path = STAGE2_DIR / "stage2_registry.json"
        with open(registry_path, "r") as f:
            return json.load(f)
    
    def _smooth_predictions(self, preds: np.ndarray, k: int = 9) -> np.ndarray:
        """Smooth predictions using majority voting in sliding window"""
        if len(preds) == 0:
            return preds
        if k <= 1:
            return preds
        
        k = k if k % 2 == 1 else k + 1
        half = k // 2
        smoothed = np.copy(preds)
        
        for i in range(len(preds)):
            start = max(0, i - half)
            end = min(len(preds), i + half + 1)
            window = preds[start:end]
            vals, counts = np.unique(window, return_counts=True)
            smoothed[i] = vals[np.argmax(counts)]
        
        return smoothed
    
    def _majority_vote(self, preds: np.ndarray) -> int:
        """Majority vote across all temporal predictions"""
        vals, counts = np.unique(preds, return_counts=True)
        return int(vals[np.argmax(counts)])
    
    def _extract_value_category(self, coarse_action: str, fine_action: str) -> str:
        """Determine value category from action type"""
        # Value-added actions (directly contribute to product)
        va_keywords = ["mount", "connect", "tight", "hand_tight", "attach"]
        # Required non-value-added (necessary but don't add value)
        rnva_keywords = ["get", "collect", "apply", "fill", "read", "inspect", "remove", "take"]
        # Non-value-added (waste)
        nva_keywords = ["excess", "lift"]
        
        action_lower = fine_action.lower()
        
        for keyword in va_keywords:
            if keyword in action_lower:
                return "VA"
        
        for keyword in rnva_keywords:
            if keyword in action_lower:
                return "RNVA"
        
        for keyword in nva_keywords:
            if keyword in action_lower:
                return "NVA"
        
        return "UNKNOWN"
    
    @torch.no_grad()
    def predict_video(self, video_path: str) -> Dict:
        """Predict action from video
        
        Args:
            video_path: Path to input video
            
        Returns:
            Dictionary with prediction results:
            {
                "coarse_action": str,
                "fine_action": str,
                "value_category": str,
                "duration": float,
                "fps": float
            }
        """
        print(f"🎬 Processing: {Path(video_path).name}")
        
        # Extract features
        print("   Extracting R3D-18 features...")
        feats, times, src_fps = extract_features_steps_r3d18(
            video_path, TARGET_FPS, CLIP_LEN, 
            self.backbone, self.r3d_mean, self.r3d_std
        )
        print(f"   Features: {feats.shape} | FPS: {src_fps:.1f}")
        
        # Get video duration
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_frames / src_fps if src_fps > 0 else 0
        cap.release()
        
        # Stage-1: Coarse prediction
        print("   Stage-1: Predicting coarse action...")
        feats_input = feats.unsqueeze(0).to(self.device)  # [1, T, 512]
        logits = self.stage1_model(feats_input)  # [1, T, num_classes]
        stage1_preds = logits.argmax(dim=-1).squeeze(0).cpu().numpy()  # [T]
        
        # Apply smoothing and majority vote
        stage1_preds_smooth = self._smooth_predictions(stage1_preds, k=9)
        coarse_idx = self._majority_vote(stage1_preds_smooth)
        coarse_label = self.stage1_i2l[coarse_idx]
        
        print(f"   Stage-1 result: {coarse_label}")
        
        # Stage-2: Fine-grained prediction
        print("   Stage-2: Predicting fine-grained action...")
        fine_label = coarse_label  # Default fallback
        
        if coarse_label in self.stage2_registry and self.stage2_registry[coarse_label].get("trained"):
            if coarse_label in self.stage2_models:
                stage2_model = self.stage2_models[coarse_label]
                stage2_l2i = self.stage2_label_maps[coarse_label]
                stage2_i2l = {v: k for k, v in stage2_l2i.items()}
                
                logits2 = stage2_model(feats_input)  # [1, T, num_classes]
                stage2_preds = logits2.argmax(dim=-1).squeeze(0).cpu().numpy()  # [T]
                fine_idx = self._majority_vote(stage2_preds)
                fine_label = stage2_i2l[fine_idx]
        
        print(f"   Stage-2 result: {fine_label}")
        
        # Determine value category
        value_category = self._extract_value_category(coarse_label, fine_label)
        
        result = {
            "coarse_action": coarse_label,
            "fine_action": fine_label,
            "value_category": value_category,
            "duration": float(video_duration),
            "fps": float(src_fps)
        }
        
        print(f"   ✅ Final prediction: {coarse_label} → {fine_label} ({value_category})")
        return result
    
    def create_annotated_video(self, input_path: str, output_path: str, prediction: Dict) -> tuple[bool, str]:
        """Create annotated video with prediction overlay
        
        Args:
            input_path: Path to input video
            output_path: Path to save annotated video
            prediction: Prediction results from predict_video()
            
        Returns:
            Tuple of (success: bool, actual_output_path: str)
        """
        print(f"   Creating annotated video...")
        
        try:
            # Open input video
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                raise RuntimeError(f"Could not open video: {input_path}")
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Create output directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Change extension to .webm for reliable browser compatibility
            # VP8 is open, universally supported in browsers, and works with OpenCV
            if output_path.endswith('.mp4') or output_path.endswith('.avi'):
                output_path = os.path.splitext(output_path)[0] + '.webm'
            
            # Use VP8 codec (vp80) - excellent browser support (Chrome, Firefox, Edge)
            # This is much more reliable than mp4v or MJPEG for web playback
            fourcc = cv2.VideoWriter_fourcc(*'VP80')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            if not out.isOpened():
                # Fallback to VP9 if VP8 fails
                print("   VP80 codec failed, trying VP90...")
                fourcc = cv2.VideoWriter_fourcc(*'VP90')
                out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
                
                if not out.isOpened():
                    raise RuntimeError("Could not initialize video writer with VP8/VP9")
            
            print(f"   Using VP8/VP9 codec in WebM container for universal browser compatibility")
            
            # Overlay parameters
            coarse_action = prediction["coarse_action"]
            fine_action = prediction["fine_action"]
            value_category = prediction["value_category"]
            
            # Get color for value category
            color = OVERLAY_COLORS.get(value_category, OVERLAY_COLORS["UNKNOWN"])
            
            # Text settings
            font = cv2.FONT_HERSHEY_SIMPLEX
            line_height = 35
            
            # Overlay text
            overlay_lines = [
                f"COARSE ACTION: {coarse_action}",
                f"FINE ACTION  : {fine_action}",
                f"VALUE TYPE   : {value_category}"
            ]
            
            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Add background for better text visibility
                overlay = frame.copy()
                cv2.rectangle(overlay, (10, 10), (700, 130), (0, 0, 0), -1)
                frame = cv2.addWeighted(frame, BACKGROUND_ALPHA, overlay, TEXT_ALPHA, 0)
                
                # Add text with outline
                for i, line in enumerate(overlay_lines):
                    y_pos = 45 + i * line_height
                    # White outline
                    cv2.putText(frame, line, (20, y_pos), font, FONT_SCALE, 
                               (255, 255, 255), FONT_THICKNESS + 2)
                    # Colored text on top
                    cv2.putText(frame, line, (20, y_pos), font, FONT_SCALE, 
                               color, FONT_THICKNESS)
                
                # Write frame
                out.write(frame)
                frame_count += 1
                
                # Progress indicator
                if frame_count % 100 == 0:
                    progress = (frame_count / total_frames) * 100
                    print(f"     Progress: {progress:.1f}%")
            
            # Cleanup
            cap.release()
            out.release()
            
            print(f"   ✅ Annotated video saved: {output_path}")
            return True, output_path
            
        except Exception as e:
            print(f"   ❌ Error creating annotated video: {e}")
            import traceback
            traceback.print_exc()
            return False, ""
