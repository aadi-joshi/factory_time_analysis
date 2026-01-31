"""
Two-Stage Temporal Action Recognition - Deployment Training Script
Updated for industry deployment with FIXED_T = 16 and flat dataset structure
"""

import os
import re
import json
import math
import glob
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Tuple

import numpy as np
import pandas as pd
import cv2
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from tqdm.auto import tqdm
from torchvision.models.video import r3d_18, R3D_18_Weights

# ============================================================
# CONFIGURATION (UPDATED FOR DEPLOYMENT)
# ============================================================
SEED = 42
np.random.seed(SEED)
torch.manual_seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)

# Paths
CLIPS_DIR = "dataset"  # Flat structure with all videos
OUT_DIR = "outputs_deployment"
CACHE_DIR = os.path.join(OUT_DIR, "feat_cache")
STAGE1_DIR = os.path.join(OUT_DIR, "stage1")
STAGE2_DIR = os.path.join(OUT_DIR, "stage2")

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(STAGE1_DIR, exist_ok=True)
os.makedirs(STAGE2_DIR, exist_ok=True)

# Feature extraction params
TARGET_FPS = 8
CLIP_LEN = 16
FEATURE_DIM = 512

# Training params (UPDATED)
FIXED_T = 16  # CHANGED FROM 64 TO 16 (INDUSTRY REQUEST)
BATCH_SIZE = 4
EPOCHS_1 = 40
EPOCHS_2 = 50
LR = 1e-3
WEIGHT_DECAY = 1e-4

# Device
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🔧 DEVICE: {DEVICE}")
print(f"🔧 PyTorch: {torch.__version__} | CUDA: {torch.version.cuda} | Available: {torch.cuda.is_available()}")

# Enable mixed precision for RTX 4050
USE_AMP = torch.cuda.is_available()
if USE_AMP:
    print("🔧 Mixed Precision (FP16): ENABLED")

print(f"🔧 FIXED_T updated to: {FIXED_T} (deployment optimization)")

# ============================================================
# LABEL PARSING (UPDATED FOR FLAT STRUCTURE)
# ============================================================
def parse_filename_label(filename: str) -> Tuple[str, str, str]:
    """
    Parse filename to extract action, value category, and ID
    Format: <action_name>_<va|rnva|nva>_<id>.mp4
    
    Returns:
        fine_label: full action name (without value category and ID)
        value_category: VA, RNVA, or NVA
        video_id: numeric ID
    """
    stem = Path(filename).stem.lower()
    
    # Split by underscore
    parts = stem.split("_")
    
    if len(parts) < 3:
        return "unknown", "UNKNOWN", "000"
    
    # Last part is ID
    video_id = parts[-1]
    
    # Second to last is value category
    value_suffix = parts[-2]
    if value_suffix in ["va", "rnva", "nva"]:
        value_category = value_suffix.upper()
        # Everything before value category is action name
        action_parts = parts[:-2]
    else:
        # Fallback if format is different
        value_category = "UNKNOWN"
        action_parts = parts[:-1]
    
    fine_label = "_".join(action_parts)
    
    return fine_label, value_category, video_id

def stage1_from_fine_label(fine_label: str) -> str:
    """FirstWord strategy: extract first token"""
    if not fine_label:
        return "unknown"
    parts = fine_label.split("_")
    return parts[0] if len(parts) else "unknown"

# ============================================================
# VIDEO SCANNING (UPDATED FOR FLAT STRUCTURE)
# ============================================================
def list_videos_flat(root: str) -> List[str]:
    """Find all video files in flat directory structure"""
    exts = ["*.mp4", "*.avi", "*.mov", "*.mkv", "*.MP4", "*.AVI", "*.MOV", "*.MKV"]
    out = []
    for e in exts:
        out.extend(glob.glob(os.path.join(root, e)))
    return sorted(out)

# ============================================================
# R3D-18 FEATURE EXTRACTOR (UNCHANGED)
# ============================================================
def build_r3d18_feature_extractor(device: str = "cpu"):
    """Build R3D-18 backbone for 512-D feature extraction"""
    weights = R3D_18_Weights.KINETICS400_V1
    base = r3d_18(weights=weights)
    base.fc = nn.Identity()
    base.eval().to(device)
    
    # Kinetics-400 normalization
    mean = torch.tensor([0.43216, 0.394666, 0.37645], dtype=torch.float32).view(1,3,1,1,1).to(device)
    std = torch.tensor([0.22803, 0.22145, 0.216989], dtype=torch.float32).view(1,3,1,1,1).to(device)
    return base, mean, std

# ============================================================
# VIDEO PROCESSING (UNCHANGED)
# ============================================================
def read_video_meta(video_path: str):
    """Read video metadata"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps is None or fps <= 1e-6:
        fps = 25.0
    nframes = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return float(fps), int(nframes), int(w), int(h)

def sample_frame_indices(src_fps: float, nframes: int, target_fps: int) -> np.ndarray:
    """Uniform temporal sampling"""
    if nframes <= 0:
        return np.array([], dtype=np.int64)
    step = max(1, int(round(src_fps / float(target_fps))))
    return np.arange(0, nframes, step, dtype=np.int64)

def load_frames_rgb(video_path: str, frame_indices: np.ndarray, resize_hw=(112,112)) -> torch.Tensor:
    """Load specific frames from video"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    
    frames = []
    idx_set = set(frame_indices.tolist())
    cur = 0
    want_ptr = 0
    want_len = len(frame_indices)
    
    while True:
        ok, frame_bgr = cap.read()
        if not ok:
            break
        if cur in idx_set:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            if resize_hw is not None:
                frame_rgb = cv2.resize(frame_rgb, resize_hw, interpolation=cv2.INTER_AREA)
            frames.append(frame_rgb)
            want_ptr += 1
            if want_ptr >= want_len:
                break
        cur += 1
    
    cap.release()
    if len(frames) == 0:
        return torch.empty((0, resize_hw[1], resize_hw[0], 3), dtype=torch.uint8)
    arr = np.stack(frames, axis=0)
    return torch.from_numpy(arr).to(torch.uint8)

@torch.no_grad()
def extract_features_steps_r3d18(video_path: str, target_fps: int, clip_len: int,
                                  backbone, r3d_mean, r3d_std) -> Tuple[torch.Tensor, torch.Tensor, float]:
    """Extract R3D-18 features from video"""
    src_fps, nframes, _, _ = read_video_meta(video_path)
    idx = sample_frame_indices(src_fps, nframes, target_fps)
    if len(idx) == 0:
        return torch.zeros((1, FEATURE_DIM), dtype=torch.float32), torch.zeros((1,), dtype=torch.float32), float(src_fps)
    
    frames = load_frames_rgb(video_path, idx, resize_hw=(112, 112))
    if frames.shape[0] == 0:
        return torch.zeros((1, FEATURE_DIM), dtype=torch.float32), torch.zeros((1,), dtype=torch.float32), float(src_fps)
    
    x = frames.float() / 255.0
    x = x.permute(0, 3, 1, 2)  # [N, 3, 112, 112]
    N = x.shape[0]
    n_steps = int(math.ceil(N / clip_len))
    
    sampled_times = (idx.astype(np.float32) / float(src_fps))
    
    feats, ts = [], []
    for s in range(n_steps):
        a = s * clip_len
        b = min((s+1) * clip_len, N)
        chunk = x[a:b]
        if chunk.shape[0] < clip_len:
            pad = chunk[-1:].repeat(clip_len - chunk.shape[0], 1, 1, 1)
            chunk = torch.cat([chunk, pad], dim=0)
        
        chunk = chunk.permute(1, 0, 2, 3).unsqueeze(0).to(DEVICE)  # [1, 3, T, H, W]
        chunk = (chunk - r3d_mean) / r3d_std
        
        f = backbone(chunk)  # [1, 512]
        feats.append(f.squeeze(0).detach().cpu())
        
        t0 = float(sampled_times[a]) if a < len(sampled_times) else float(sampled_times[-1])
        ts.append(t0)
    
    feats = torch.stack(feats, dim=0).float()
    ts = torch.tensor(ts, dtype=torch.float32)
    return feats, ts, float(src_fps)

def cache_key(video_path: str, target_fps: int, clip_len: int) -> str:
    """Generate cache key"""
    s = f"{Path(video_path).as_posix()}|fps={target_fps}|len={clip_len}"
    h = hashlib.md5(s.encode("utf-8")).hexdigest()
    return f"vid_{h}__fps{target_fps}__len{clip_len}"

def get_cached_features(video_path: str, target_fps: int, clip_len: int,
                        backbone, r3d_mean, r3d_std):
    """Get or compute cached features"""
    key = cache_key(video_path, target_fps, clip_len)
    feat_path = os.path.join(CACHE_DIR, key + ".pt")
    meta_path = os.path.join(CACHE_DIR, key + ".json")
    
    if os.path.exists(feat_path) and os.path.exists(meta_path):
        try:
            data = torch.load(feat_path, map_location="cpu")
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            feats = data["feats"]
            ts = data["ts"]
            src_fps = float(meta.get("src_fps", 0.0))
            if feats.ndim != 2 or ts.ndim != 1 or feats.shape[0] != ts.shape[0]:
                raise ValueError("Cache sanity failed")
            return feats, ts, src_fps
        except Exception as e:
            print(f"⚠️ Cache load failed, recomputing: {Path(video_path).name}")
    
    feats, ts, src_fps = extract_features_steps_r3d18(video_path, target_fps, clip_len,
                                                       backbone, r3d_mean, r3d_std)
    torch.save({"feats": feats, "ts": ts}, feat_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"src_fps": float(src_fps)}, f, indent=2)
    return feats, ts, float(src_fps)

# ============================================================
# DATASET (UPDATED FOR FIXED_T = 16)
# ============================================================
def pad_or_crop_2d(x: torch.Tensor, T: int) -> torch.Tensor:
    """Pad or crop to fixed length"""
    t, d = x.shape
    if t == T:
        return x
    if t > T:
        return x[:T]
    pad = x[-1:].repeat(T - t, 1)
    return torch.cat([x, pad], dim=0)

def pad_or_crop_1d(x: torch.Tensor, T: int) -> torch.Tensor:
    """Pad or crop 1D tensor"""
    t = x.shape[0]
    if t == T:
        return x
    if t > T:
        return x[:T]
    pad = x[-1:].repeat(T - t)
    return torch.cat([x, pad], dim=0)

def collate_fixedT(batch):
    """Collate function"""
    xs = torch.stack([b["x"] for b in batch], dim=0)
    ys = torch.tensor([b["y"] for b in batch], dtype=torch.long)
    ts = torch.stack([b["ts"] for b in batch], dim=0)
    return {"x": xs, "y": ys, "ts": ts, "video": [b["video"] for b in batch]}

class ClipDataset(Dataset):
    def __init__(self, df: pd.DataFrame, label_col: str, label_to_id: Dict[str, int],
                 target_fps: int, clip_len: int, fixed_T: int,
                 backbone, r3d_mean, r3d_std):
        self.df = df.reset_index(drop=True)
        self.label_col = label_col
        self.label_to_id = label_to_id
        self.target_fps = int(target_fps)
        self.clip_len = int(clip_len)
        self.fixed_T = int(fixed_T)
        self.backbone = backbone
        self.r3d_mean = r3d_mean
        self.r3d_std = r3d_std
    
    def __len__(self):
        return len(self.df)
    
    def __getitem__(self, idx: int):
        row = self.df.iloc[idx]
        video_path = str(row["video"])
        label_name = str(row[self.label_col])
        if label_name not in self.label_to_id:
            raise KeyError(f"Label '{label_name}' not found in label map for '{self.label_col}'")
        y = int(self.label_to_id[label_name])
        
        feats, ts, src_fps = get_cached_features(video_path, self.target_fps, self.clip_len,
                                                  self.backbone, self.r3d_mean, self.r3d_std)
        feats = pad_or_crop_2d(feats, self.fixed_T)
        ts = pad_or_crop_1d(ts, self.fixed_T)
        
        return {"x": feats.float(), "y": y, "video": video_path, "ts": ts.float(), "src_fps": float(src_fps)}

# ============================================================
# TEMPORAL CLASSIFIER (UNCHANGED)
# ============================================================
class TemporalClassifier(nn.Module):
    """Simple MLP per timestep"""
    def __init__(self, in_dim: int, num_classes: int, hidden: int = 256):
        super().__init__()
        self.net = nn.Sequential(
            nn.LayerNorm(in_dim),
            nn.Linear(in_dim, hidden),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden, num_classes),
        )
    
    def forward(self, x):
        B, T, D = x.shape
        y = self.net(x.reshape(B*T, D))
        return y.reshape(B, T, -1)

# ============================================================
# TRAINING (UNCHANGED LOGIC)
# ============================================================
def majority_vote(pred_steps: np.ndarray) -> int:
    """Majority voting across timesteps"""
    vals, counts = np.unique(pred_steps, return_counts=True)
    return int(vals[np.argmax(counts)])

def run_epoch(model, loader, optimizer=None, scaler=None):
    """Run one epoch"""
    train = optimizer is not None
    model.train(train)
    
    total_loss, total_correct, total = 0.0, 0, 0
    if len(loader) == 0:
        return float("nan"), 0.0
    
    for batch in tqdm(loader, leave=False, desc="Training" if train else "Validating"):
        x = batch["x"].to(DEVICE)
        y = batch["y"].to(DEVICE)
        B, T, _ = x.shape
        
        if train and USE_AMP:
            with torch.cuda.amp.autocast():
                logits = model(x)
                y_steps = y.view(B, 1).repeat(1, T)
                loss = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), y_steps.reshape(-1))
            
            optimizer.zero_grad()
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            logits = model(x)
            y_steps = y.view(B, 1).repeat(1, T)
            loss = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), y_steps.reshape(-1))
            
            if train:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
        
        total_loss += float(loss.item()) * B
        
        with torch.no_grad():
            pred_steps = logits.argmax(dim=-1).detach().cpu().numpy()
            for i in range(B):
                pred_clip = majority_vote(pred_steps[i])
                total_correct += int(pred_clip == int(y[i].item()))
                total += 1
    
    return total_loss / max(total, 1), total_correct / max(total, 1)

def train_model(model, train_loader, epochs: int, best_path: str, last_path: str):
    """Train model on full dataset"""
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    scaler = torch.cuda.amp.GradScaler() if USE_AMP else None
    
    hist = {"train_loss": [], "train_acc": []}
    best_loss = float("inf")
    
    print(f"✅ Starting training | Batches: {len(train_loader)} | Epochs: {epochs}")
    
    start_time = time.time()
    for ep in range(1, epochs + 1):
        tr_loss, tr_acc = run_epoch(model, train_loader, optimizer=opt, scaler=scaler)
        hist["train_loss"].append(tr_loss)
        hist["train_acc"].append(tr_acc)
        
        print(f"Epoch {ep:03d}/{epochs} | loss {tr_loss:.4f} | acc {tr_acc:.3f}")
        
        if tr_loss < best_loss:
            best_loss = tr_loss
            torch.save(model.state_dict(), best_path)
            print(f"  ✅ Best model saved -> {best_path}")
        
        torch.save(model.state_dict(), last_path)
    
    elapsed = time.time() - start_time
    print(f"✅ Training complete | Time: {elapsed/60:.1f}min | Best loss: {best_loss:.4f}")
    return hist

# ============================================================
# MAIN TRAINING PIPELINE
# ============================================================
def main():
    print("=" * 80)
    print("TWO-STAGE TEMPORAL ACTION RECOGNITION - DEPLOYMENT TRAINING")
    print("=" * 80)
    print(f"FIXED_T = {FIXED_T} (deployment optimization)")
    
    # Step 1: Scan dataset (flat structure)
    print("\n📂 Step 1: Scanning flat dataset...")
    videos = list_videos_flat(CLIPS_DIR)
    print(f"   Found {len(videos)} video clips")
    assert len(videos) > 0, "No videos found. Check CLIPS_DIR path."
    
    # Step 2: Parse labels from filenames
    print("\n🏷️  Step 2: Parsing labels from filenames...")
    df_data = []
    for video_path in videos:
        filename = Path(video_path).name
        fine_label, value_category, video_id = parse_filename_label(filename)
        stage1_label = stage1_from_fine_label(fine_label)
        
        df_data.append({
            "video": video_path,
            "filename": filename,
            "fine_label": fine_label,
            "stage1_label": stage1_label,
            "value_category": value_category,
            "video_id": video_id
        })
    
    df = pd.DataFrame(df_data)
    
    print(f"   Total clips: {len(df)}")
    print(f"   Unique fine labels: {df['fine_label'].nunique()}")
    print(f"   Unique stage1 labels (FirstWord): {df['stage1_label'].nunique()}")
    print(f"   Value categories: {df['value_category'].value_counts().to_dict()}")
    
    # Step 3: Build R3D-18 feature extractor
    print("\n🧠 Step 3: Building R3D-18 feature extractor...")
    backbone_r3d, r3d_mean, r3d_std = build_r3d18_feature_extractor(DEVICE)
    print(f"   ✅ R3D-18 ready | Feature dim: {FEATURE_DIM}")
    
    # Step 4: Train Stage-1 (FirstWord coarse labels)
    print("\n" + "=" * 80)
    print("STAGE 1: TRAINING COARSE CLASSIFIER (FirstWord)")
    print("=" * 80)
    
    stage1_labels = sorted(df["stage1_label"].unique().tolist())
    stage1_l2i = {lbl: i for i, lbl in enumerate(stage1_labels)}
    
    with open(os.path.join(STAGE1_DIR, "label_map.json"), "w") as f:
        json.dump(stage1_l2i, f, indent=2)
    
    train_ds1 = ClipDataset(df, label_col="stage1_label", label_to_id=stage1_l2i,
                            target_fps=TARGET_FPS, clip_len=CLIP_LEN, fixed_T=FIXED_T,
                            backbone=backbone_r3d, r3d_mean=r3d_mean, r3d_std=r3d_std)
    train_loader1 = DataLoader(train_ds1, batch_size=BATCH_SIZE, shuffle=True,
                               num_workers=0, collate_fn=collate_fixedT)
    
    print(f"   Classes: {len(stage1_l2i)}")
    print(f"   Training clips: {len(train_ds1)}")
    
    stage1_model = TemporalClassifier(in_dim=FEATURE_DIM, num_classes=len(stage1_l2i), hidden=256).to(DEVICE)
    
    BEST1 = os.path.join(STAGE1_DIR, "best.pt")
    LAST1 = os.path.join(STAGE1_DIR, "last.pt")
    
    hist1 = train_model(stage1_model, train_loader1, epochs=EPOCHS_1, best_path=BEST1, last_path=LAST1)
    
    print(f"\n✅ Stage-1 complete | Saved: {BEST1}")
    
    # Step 5: Train Stage-2 (per-family fine classifiers)
    print("\n" + "=" * 80)
    print("STAGE 2: TRAINING FINE-GRAINED CLASSIFIERS (Per Family)")
    print("=" * 80)
    
    stage2_registry = {}
    
    for fam in tqdm(stage1_labels, desc="Training Stage-2 families"):
        df_fam = df[df["stage1_label"] == fam].copy()
        nclips = len(df_fam)
        fine_labels_fam = sorted(df_fam["fine_label"].unique().tolist())
        nclasses = len(fine_labels_fam)
        
        print(f"\n📦 Family: {fam} | Clips: {nclips} | Fine classes: {nclasses}")
        
        if nclasses <= 1:
            print("   ⏭️  Skipping (only 1 fine label)")
            stage2_registry[fam] = {"trained": False, "reason": "single_class", "n_clips": nclips, "n_classes": nclasses}
            continue
        
        if nclips < 2:
            print("   ⏭️  Skipping (too few clips)")
            stage2_registry[fam] = {"trained": False, "reason": "too_few_clips", "n_clips": nclips, "n_classes": nclasses}
            continue
        
        # Train this family
        out_dir = os.path.join(STAGE2_DIR, fam)
        os.makedirs(out_dir, exist_ok=True)
        
        fine_l2i = {lbl: i for i, lbl in enumerate(fine_labels_fam)}
        with open(os.path.join(out_dir, "label_map.json"), "w") as f:
            json.dump(fine_l2i, f, indent=2)
        
        train_ds2 = ClipDataset(df_fam, label_col="fine_label", label_to_id=fine_l2i,
                                target_fps=TARGET_FPS, clip_len=CLIP_LEN, fixed_T=FIXED_T,
                                backbone=backbone_r3d, r3d_mean=r3d_mean, r3d_std=r3d_std)
        train_loader2 = DataLoader(train_ds2, batch_size=BATCH_SIZE, shuffle=True,
                                   num_workers=0, collate_fn=collate_fixedT)
        
        stage2_model = TemporalClassifier(in_dim=FEATURE_DIM, num_classes=nclasses, hidden=256).to(DEVICE)
        
        BEST2 = os.path.join(out_dir, "best.pt")
        LAST2 = os.path.join(out_dir, "last.pt")
        
        hist2 = train_model(stage2_model, train_loader2, epochs=EPOCHS_2, best_path=BEST2, last_path=LAST2)
        
        stage2_registry[fam] = {
            "trained": True,
            "n_clips": nclips,
            "n_classes": nclasses,
            "best_path": BEST2,
            "last_path": LAST2,
            "label_map_path": os.path.join(out_dir, "label_map.json")
        }
    
    with open(os.path.join(STAGE2_DIR, "stage2_registry.json"), "w") as f:
        json.dump(stage2_registry, f, indent=2)
    
    print("\n" + "=" * 80)
    print("✅ DEPLOYMENT TRAINING COMPLETE")
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   FIXED_T: {FIXED_T} (deployment optimized)")
    print(f"   Stage-1 model: {BEST1}")
    print(f"   Stage-2 registry: {os.path.join(STAGE2_DIR, 'stage2_registry.json')}")
    print(f"   Total families trained: {sum(1 for v in stage2_registry.values() if v.get('trained'))}")
    print(f"\n🎯 Models ready for deployment inference")

if __name__ == "__main__":
    main()