# Two-Stage Temporal Action Recognition System

## Model Overview

This document describes the complete **two-stage temporal action recognition pipeline** used for industrial assembly process analysis. It also lists the **exact model artifacts** required to share or deploy the system with another user.

---

## 📂 Essential Models for Sharing

### Stage-1 Model (Coarse Classification)

```
outputs_deployment/stage1/
├── best.pt           # Main Stage-1 model weights (REQUIRED)
├── label_map.json    # Coarse action → class ID mapping (REQUIRED)
└── last.pt           # Latest checkpoint (optional)
```

**Purpose**
Predicts one of **14 coarse-grained action categories** from an input video.

**Coarse Action Classes**

```
apply, attach, collect, excess, fill, get, hand,
inspect, lift, mount, read, remove, take, tight
```

---

### Stage-2 Models (Fine-Grained Classification)

```
outputs_deployment/stage2/
├── stage2_registry.json      # Registry mapping coarse → fine models (REQUIRED)
├── apply/
│   ├── best.pt
│   └── label_map.json
├── attach/
│   ├── best.pt
│   └── label_map.json
├── collect/
│   ├── best.pt
│   └── label_map.json
├── fill/
│   ├── best.pt
│   └── label_map.json
├── get/
│   ├── best.pt
│   └── label_map.json
├── hand/
│   ├── best.pt
│   └── label_map.json
├── mount/
│   ├── best.pt
│   └── label_map.json
└── tight/
    ├── best.pt
    └── label_map.json
```

Each directory contains:

* `best.pt` – trained family-specific classifier
* `label_map.json` – fine-grained action label mapping

---

## 🎯 Two-Stage Inference Pipeline

### Stage-1: Coarse Action Classification

**Input**

* Video file (any format, any resolution)

**Processing**

* Video is resampled to **8 FPS**
* Frames are resized to **112 × 112**
* Video is divided into **16 temporal segments**
* R3D-18 backbone extracts **512-D features per segment**

**Output**

* One coarse action label (example: `hand`, `mount`, `get`)

---

### Stage-2: Fine-Grained Action Classification

**Input**

* Same extracted video features
* Coarse action prediction from Stage-1

**Processing**

* `stage2_registry.json` selects the correct family model
* Family-specific MLP performs fine-grained classification

**Output**

* Detailed action label

Examples:

* `hand_tight_bolt`
* `mount_o_ring_to_pipe`

---

## 📊 Stage-2 Training Coverage

### ✅ Trained Families

| Family  | Fine Actions | Training Clips |
| ------- | ------------ | -------------- |
| apply   | 5            | 10             |
| attach  | 2            | 4              |
| collect | 5            | 10             |
| fill    | 2            | 4              |
| get     | 8            | 16             |
| hand    | 8            | 16             |
| mount   | 6            | 14             |
| tight   | 6            | 12             |

### ❌ Untrained Families (Single-Class Only)

These families contain only one action and therefore **do not require Stage-2 models**:

```
excess, inspect, lift, read, remove, take
```

---

## 🔧 Technical Specifications

* **Backbone**: R3D-18 (pretrained 3D CNN)
* **Classifier**: Multi-Layer Perceptron (MLP)
* **Temporal Segments**: 16 (FIXED_T)
* **Feature Dimension**: 512-D per segment
* **Target FPS**: 8
* **Input Resolution**: Auto-resized to 112 × 112
* **Total Model Size**: ~6.9 MB (all models combined)

---

## ✅ Deployment Notes

* Stage-1 model is mandatory for all predictions
* Stage-2 models are loaded dynamically based on Stage-1 output
* Missing Stage-2 families default to coarse action output
* System is optimized for **industrial assembly monitoring and analysis**

---

**End of Document**
