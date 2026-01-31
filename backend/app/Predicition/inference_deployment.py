"""
Two-Stage Temporal Action Recognition - Deployment Inference Script
Generates both JSON timelines and annotated video overlays for industry demos
"""

import os
import json
import numpy as np
import cv2
import torch
import torch.nn as nn
from pathlib import Path
from typing import Dict, List, Tuple
from train_deployment_model import (
    build_r3d18_feature_extractor,
    extract_features_steps_r3d18,
    TemporalClassifier,
    DEVICE, TARGET_FPS, CLIP_LEN, FEATURE_DIM, FIXED_T
)

# Paths
STAGE1_DIR = "outputs_deployment/stage1"
STAGE2_DIR = "outputs_deployment/stage2"
TEST_DIR = "test"
RESULTS_DIR = "inference_results"
JSON_DIR = os.path.join(RESULTS_DIR, "json")
VIDEO_DIR = os.path.join(RESULTS_DIR, "videos")

# Create output directories
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

# Smoothing parameters
SMOOTH_K_STAGE1 = 9
MIN_SEG_DUR_S = 1.0

# Video overlay parameters
OVERLAY_COLORS = {
    "VA": (0, 255, 0),          # Bright Green
    "RNVA": (0, 140, 255),      # Bright Orange (BGR format)
    "NVA": (0, 0, 255),         # Bright Red
    "UNKNOWN": (128, 128, 128)  # Gray
}

# Text styling for better visibility
FONT_SCALE = 0.8
FONT_THICKNESS = 3
BACKGROUND_ALPHA = 0.7  # More opaque background
TEXT_ALPHA = 0.3        # Less transparent overlay

def load_label_map(path: str) -> Dict:
    """Load label map from JSON"""
    with open(path, "r") as f:
        return json.load(f)

def load_stage2_registry() -> Dict:
    """Load Stage-2 model registry"""
    registry_path = os.path.join(STAGE2_DIR, "stage2_registry.json")
    with open(registry_path, "r") as f:
        return json.load(f)

def smooth_predictions(preds: np.ndarray, k: int = 9) -> np.ndarray:
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

def majority_vote_all_chunks(preds: np.ndarray) -> int:
    """Majority vote across ALL temporal predictions for single video output"""
    vals, counts = np.unique(preds, return_counts=True)
    return int(vals[np.argmax(counts)])

def extract_value_category(video_filename: str) -> str:
    """Extract value category from video filename"""
    # Extract filename without extension
    filename = Path(video_filename).stem
    
    # Look for value category patterns in filename
    if "_va_" in filename:
        return "VA"
    elif "_rnva_" in filename:
        return "RNVA"
    elif "_nva_" in filename:
        return "NVA"
    
    # If no explicit category found, infer from action type
    # This is a fallback for test videos without explicit categories
    action_lower = filename.lower()
    
    # Value-added actions (directly contribute to product)
    va_keywords = ["mount", "connect", "tight", "hand_tight", "oil_fill"]
    # Required non-value-added (necessary but don't add value)
    rnva_keywords = ["get", "collect", "apply", "fill", "read", "inspect", "remove", "take"]
    # Non-value-added (waste)
    nva_keywords = ["excess", "unpack", "walk"]
    
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
def predict_stage1(feats: torch.Tensor, model: nn.Module) -> np.ndarray:
    """Stage-1 prediction: coarse action classification"""
    model.eval()
    feats = feats.unsqueeze(0).to(DEVICE)  # [1, T, 512]
    logits = model(feats)  # [1, T, num_classes]
    preds = logits.argmax(dim=-1).squeeze(0).cpu().numpy()  # [T]
    return preds

@torch.no_grad()
def predict_stage2(feats: torch.Tensor, model: nn.Module) -> int:
    """Stage-2 prediction: fine-grained action (majority vote)"""
    model.eval()
    feats = feats.unsqueeze(0).to(DEVICE)  # [1, T, 512]
    logits = model(feats)  # [1, T, num_classes]
    preds = logits.argmax(dim=-1).squeeze(0).cpu().numpy()  # [T]
    
    # Majority vote across all temporal predictions
    return majority_vote_all_chunks(preds)

def inference_single_video(video_path: str, backbone, r3d_mean, r3d_std,
                          stage1_model, stage1_l2i, stage1_i2l,
                          stage2_registry, stage2_models, stage2_label_maps) -> Dict:
    """
    Two-stage inference on a single video
    Returns single prediction per video (aggregated)
    """
    print(f"\n🎬 Processing: {Path(video_path).name}")
    
    # Extract features
    print("   Extracting R3D-18 features...")
    feats, times, src_fps = extract_features_steps_r3d18(
        video_path, TARGET_FPS, CLIP_LEN, backbone, r3d_mean, r3d_std
    )
    print(f"   Features: {feats.shape} | Times: {times.shape} | FPS: {src_fps:.1f}")
    
    # Get video duration
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_duration = total_frames / src_fps
    cap.release()
    
    # Stage-1: Coarse prediction
    print("   Stage-1: Predicting coarse actions...")
    stage1_preds = predict_stage1(feats, stage1_model)
    
    # Apply temporal smoothing
    stage1_preds_smooth = smooth_predictions(stage1_preds, k=SMOOTH_K_STAGE1)
    
    # Aggregate to single prediction via majority vote
    coarse_idx = majority_vote_all_chunks(stage1_preds_smooth)
    coarse_label = stage1_i2l[coarse_idx]
    
    print(f"   Stage-1 result: {coarse_label}")
    
    # Stage-2: Fine-grained prediction
    print("   Stage-2: Predicting fine-grained action...")
    fine_label = coarse_label  # Default fallback
    
    if coarse_label in stage2_registry and stage2_registry[coarse_label].get("trained"):
        if coarse_label in stage2_models:
            stage2_model = stage2_models[coarse_label]
            stage2_l2i = stage2_label_maps[coarse_label]
            stage2_i2l = {v: k for k, v in stage2_l2i.items()}
            
            fine_idx = predict_stage2(feats, stage2_model)
            fine_label = stage2_i2l[fine_idx]
    
    print(f"   Stage-2 result: {fine_label}")
    
    # Extract value category from video filename
    value_category = extract_value_category(video_path)
    
    # Create single prediction result
    result = {
        "video_path": video_path,
        "video_name": Path(video_path).name,
        "duration": float(video_duration),
        "coarse_action": coarse_label,
        "fine_action": fine_label,
        "value_category": value_category,
        "temporal_chunks": int(len(feats)),
        "fps": float(src_fps)
    }
    
    print(f"   ✅ Final prediction: {coarse_label} → {fine_label} ({value_category})")
    return result

def create_video_overlay(video_path: str, prediction: Dict, output_path: str):
    """Create annotated video with prediction overlay"""
    print(f"   Creating video overlay...")
    
    # Open input video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    
    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Setup video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    # Overlay parameters
    coarse_action = prediction["coarse_action"]
    fine_action = prediction["fine_action"]
    value_category = prediction["value_category"]
    
    # Get color for value category
    color = OVERLAY_COLORS.get(value_category, OVERLAY_COLORS["UNKNOWN"])
    
    # Text settings for better visibility
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = FONT_SCALE
    thickness = FONT_THICKNESS
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
        
        # Add more opaque background for better text visibility
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (700, 130), (0, 0, 0), -1)
        frame = cv2.addWeighted(frame, BACKGROUND_ALPHA, overlay, TEXT_ALPHA, 0)
        
        # Add white outline for text (better contrast)
        for i, line in enumerate(overlay_lines):
            y_pos = 45 + i * line_height
            # White outline
            cv2.putText(frame, line, (20, y_pos), font, font_scale, (255, 255, 255), thickness + 2)
            # Colored text on top
            cv2.putText(frame, line, (20, y_pos), font, font_scale, color, thickness)
        
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
    
    print(f"   ✅ Video overlay saved: {output_path}")

def save_json_timeline(prediction: Dict, output_path: str):
    """Save prediction as JSON timeline (compatible with existing format)"""
    # Create timeline format (single segment for entire video)
    timeline = [{
        "start": 0.0,
        "end": prediction["duration"],
        "duration": prediction["duration"],
        "coarse_action": prediction["coarse_action"],
        "fine_action": prediction["fine_action"],
        "value_category": prediction["value_category"],
        "num_frames": prediction["temporal_chunks"]
    }]
    
    with open(output_path, "w") as f:
        json.dump(timeline, f, indent=2)
    
    print(f"   ✅ JSON timeline saved: {output_path}")

def main():
    print("=" * 80)
    print("TWO-STAGE TEMPORAL ACTION RECOGNITION - DEPLOYMENT INFERENCE")
    print("=" * 80)
    print(f"FIXED_T = {FIXED_T} (deployment mode)")
    
    # Load R3D-18 backbone
    print("\n🧠 Loading R3D-18 feature extractor...")
    backbone_r3d, r3d_mean, r3d_std = build_r3d18_feature_extractor(DEVICE)
    print("   ✅ R3D-18 ready")
    
    # Load Stage-1 model
    print("\n📦 Loading Stage-1 model...")
    stage1_l2i = load_label_map(os.path.join(STAGE1_DIR, "label_map.json"))
    stage1_i2l = {v: k for k, v in stage1_l2i.items()}
    stage1_model = TemporalClassifier(in_dim=FEATURE_DIM, num_classes=len(stage1_l2i), hidden=256).to(DEVICE)
    stage1_model.load_state_dict(torch.load(os.path.join(STAGE1_DIR, "best.pt"), map_location=DEVICE, weights_only=False))
    stage1_model.eval()
    print(f"   ✅ Stage-1 loaded | Classes: {len(stage1_l2i)}")
    
    # Load Stage-2 models
    print("\n📦 Loading Stage-2 models...")
    stage2_registry = load_stage2_registry()
    stage2_models = {}
    stage2_label_maps = {}
    
    for family, info in stage2_registry.items():
        if info.get("trained"):
            family_dir = os.path.join(STAGE2_DIR, family)
            label_map = load_label_map(os.path.join(family_dir, "label_map.json"))
            model = TemporalClassifier(in_dim=FEATURE_DIM, num_classes=len(label_map), hidden=256).to(DEVICE)
            model.load_state_dict(torch.load(os.path.join(family_dir, "best.pt"), map_location=DEVICE, weights_only=False))
            model.eval()
            stage2_models[family] = model
            stage2_label_maps[family] = label_map
            print(f"   ✅ {family}: {len(label_map)} classes")
    
    print(f"\n   Total Stage-2 models loaded: {len(stage2_models)}")
    
    # Find test videos
    print(f"\n🔍 Scanning test directory: {TEST_DIR}")
    test_videos = []
    if os.path.exists(TEST_DIR):
        for ext in ["*.mp4", "*.avi", "*.mov", "*.MP4", "*.AVI", "*.MOV"]:
            import glob
            test_videos.extend(glob.glob(os.path.join(TEST_DIR, ext)))
    
    if len(test_videos) == 0:
        print("   ⚠️  No test videos found")
        return
    
    print(f"   Found {len(test_videos)} test videos")
    
    # Process each test video
    all_predictions = []
    
    for video_path in test_videos:
        try:
            # Run inference
            prediction = inference_single_video(
                video_path, backbone_r3d, r3d_mean, r3d_std,
                stage1_model, stage1_l2i, stage1_i2l,
                stage2_registry, stage2_models, stage2_label_maps
            )
            
            all_predictions.append(prediction)
            
            # Save outputs
            video_name = Path(video_path).stem
            
            # 1. JSON Timeline
            json_path = os.path.join(JSON_DIR, f"{video_name}_timeline.json")
            save_json_timeline(prediction, json_path)
            
            # 2. Video Overlay
            video_output_path = os.path.join(VIDEO_DIR, f"{video_name}_annotated.mp4")
            create_video_overlay(video_path, prediction, video_output_path)
            
            print(f"   💾 Outputs saved:")
            print(f"      - JSON: {json_path}")
            print(f"      - Video: {video_output_path}")
            
        except Exception as e:
            print(f"   ❌ Error processing {Path(video_path).name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "=" * 80)
    print("✅ DEPLOYMENT INFERENCE COMPLETE")
    print("=" * 80)
    
    if len(all_predictions) > 0:
        print(f"\n📊 Summary:")
        print(f"   Videos processed: {len(all_predictions)}")
        
        # Action distribution
        coarse_actions = [p["coarse_action"] for p in all_predictions]
        value_categories = [p["value_category"] for p in all_predictions]
        
        print(f"\n   Coarse action distribution:")
        from collections import Counter
        for action, count in Counter(coarse_actions).items():
            print(f"     {action}: {count}")
        
        print(f"\n   Value category distribution:")
        for category, count in Counter(value_categories).items():
            color_name = {"VA": "Green", "RNVA": "Orange", "NVA": "Red"}.get(category, "Gray")
            print(f"     {category}: {count} ({color_name})")
        
        print(f"\n📁 Results saved in:")
        print(f"   JSON timelines: {JSON_DIR}/")
        print(f"   Annotated videos: {VIDEO_DIR}/")
        
        print(f"\n🎯 Trained Successfully!")

if __name__ == "__main__":
    main()