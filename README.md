# VA/NVA Worker Activity Analysis System

A complete value-added (VA) and non-value-added (NVA) worker activity time study platform for production environments. It tracks workers in videos, lets you define activity zones, and produces VA/NVA time metrics per worker.

This single README is the main documentation for running, understanding, and extending the project.

---

## 1. What the system does

- Accepts factory/production videos (MP4/AVI/MOV).
- Detects all people in each frame using a YOLOv8n model.
- Tracks each person across frames using the SORT tracking algorithm so each worker gets a stable ID over time.
- Lets you draw custom polygon zones on the first video frame (e.g., Assembly, Quality Check, Idle Area).
- Lets you label which zones are value-added (VA) for each worker; everything else is treated as non-value-added (NVA).
- Computes, per worker and per video:
  - VA frames, NVA frames
  - VA seconds, NVA seconds
  - VA percentage
- Stores all results in a SQLite database and exposes them via a REST API and a React analytics dashboard.

---

## 2. Project structure

Repository root:

```text
backend/
  app/
    main.py            FastAPI app and all endpoints
    api/               API route modules
    core/
      ml_pipeline.py   Detection + tracking pipeline
      sort.py          SORT tracker implementation
      geometry.py      Zone, geometry, VA/NVA logic
    db/
      models.py        SQLAlchemy ORM models
      __init__.py      DB session and init
    models/
      schemas.py       Pydantic request/response models
    services/          Service layer (future growth)
    utils/             Helpers
  requirements.txt     Backend Python dependencies

frontend/
  src/
    main.jsx           React entry point
    App.jsx            Top‑level app + routing
    components/
      Header.jsx       Navigation header
    pages/
      Dashboard.jsx        Video list and status
      VideoUpload.jsx      Upload workflow
      ZoneEditor.jsx       Zone drawing canvas
      WorkerAssignment.jsx Zone ↔ worker mapping
      Analytics.jsx        Charts and metrics
    services/
      api.js           HTTP client for backend
  index.html
  package.json
  vite.config.js

storage/
  videos/              Uploaded videos
  frames/              Extracted frames
  portraits/           Cropped worker images (if used)

run.sh                 Helper script to run backend + frontend (POSIX shells)
setup.sh               Helper script to install dependencies (POSIX shells)
README.md              This document
yolov8n.pt             Model weights (also present in backend/)
```

The exact folder names under storage/ may vary slightly depending on how you run the system, but the backend is configured to read and write within this tree.

---

## 3. Prerequisites

You can run everything locally on a reasonably modern laptop.

Backend:
- Python 3.9 or newer
- Recommended: virtual environment (venv)

Frontend:
- Node.js 16 or newer (Node 18+ recommended)

System tools:
- ffmpeg (recommended) if you run into codec/format issues

Optional:
- A CUDA‑capable GPU if you want faster detection; CPU is supported and is the default.

---

## 4. Setup and installation

You can either use the provided shell scripts (on macOS/Linux or Git Bash/WSL on Windows) or set things up manually.

### 4.1 Clone and enter the project

```bash
git clone <your-repo-url>.git
cd movement    # or whatever folder name you cloned into
```

### 4.2 Backend setup (Python / FastAPI)

From the repository root:

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv

# On Windows (PowerShell)
venv\Scripts\Activate.ps1

# On macOS / Linux / Git Bash
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

The SQLite database (tracking.db) and storage folders are created automatically when the backend runs and starts processing videos.

### 4.3 Frontend setup (React / Vite)

From the repository root (in a new terminal):

```bash
cd frontend
npm install
```

This installs all Node dependencies for the React UI.

### 4.4 Optional: using setup.sh and run.sh

If you are on macOS/Linux or have Git Bash/WSL on Windows, you can use the helper scripts from the project root:

```bash
./setup.sh   # one‑time install for backend + frontend
./run.sh     # start backend and frontend together
```

These scripts wrap the manual steps described above.

---

## 5. Running the system locally

You need two processes: one for the backend API and one for the frontend UI.

### 5.1 Start the backend

From backend/ with the virtual environment activated:

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will expose:
- REST API base URL: http://localhost:8000/api
- Interactive API docs (Swagger): http://localhost:8000/docs

### 5.2 Start the frontend

In a second terminal, from frontend/:

```bash
cd frontend
npm run dev
```

By default, Vite will start the dev server at:
- Frontend: http://localhost:3000

### 5.3 Summary of URLs

- Frontend UI: http://localhost:3000
- API docs: http://localhost:8000/docs
- API base: http://localhost:8000/api

---

## 6. End‑to‑end workflow

Once both backend and frontend are running:

1. Open the frontend at http://localhost:3000.
2. Go to the Upload Video page.
3. Select a production video (MP4/AVI/MOV) and upload it.
   - The backend stores the video, extracts metadata (fps, duration, resolution), and saves the first frame as an image.
4. After upload, move to the Zone Editor for that video.
5. Draw polygon zones directly on the first frame (at least three points per zone), name them (e.g., Assembly, Quality Check, Idle), and save.
6. Trigger processing for the video. The backend will:
   - Run YOLOv8n person detection on each frame.
   - Run the SORT tracker to assign a persistent track ID per person.
   - Store per‑frame tracks (bounding boxes, centroids, confidences) in the tracks table.
7. Go to the Worker Assignment page for the processed video.
   - For each worker ID and each zone, tick which zones are value‑added (VA) for that worker; unticked zones are treated as NVA.
8. Click Compute Metrics.
   - The backend computes VA/NVA frames and seconds per worker, and VA percentage, and stores these in the vava_metrics table.
9. Open the Analytics page.
   - View summary cards, charts (e.g., VA vs NVA split, per‑worker bars), and detailed tables.

There is also support for merging worker IDs when a single physical worker receives multiple track IDs; see the detection and analytics logic section below.

---

## 7. Detection, tracking, and VA/NVA logic

This section explains the core logic at a high level.

### 7.1 Detection (YOLOv8n)

- Model: YOLOv8n (the lightweight "nano" variant) from the Ultralytics library.
- Task: detect people only (COCO class 0) in each frame.
- Input: frames are resized to the model’s expected resolution (e.g., 640×640) while maintaining aspect ratio.
- Output per frame: a list of detections with bounding boxes, confidence scores, and class labels.

In code terms, the DetectionService in backend/app/core/ml_pipeline.py wraps the Ultralytics YOLO model and returns a simple list of [x1, y1, x2, y2, confidence] per detection.

### 7.2 Tracking (SORT)

- Algorithm: SORT (Simple Online and Realtime Tracking).
- Core ideas:
  - A Kalman filter predicts where each existing track will be in the next frame.
  - The Hungarian algorithm matches new detections to predicted tracks based on bounding box overlap (IoU).
  - If a detection does not match any existing track, a new track is created.
  - If a track goes unmatched for more than max_age frames, it is considered ended.
- Output per frame: a list of tracks with bounding box and a stable track_id.

This is implemented in backend/app/core/sort.py and used by TrackingService in ml_pipeline.py.

### 7.3 Zones and point‑in‑polygon

- Each zone is stored as a polygon (list of [x, y] points) tied to a specific video.
- For every tracked bounding box, the system computes its centroid.
- For each centroid, it checks which zone polygons contain that point using Shapely’s Polygon.contains.
- The result is a mapping: (frame_idx, track_id) → zone_id (or None if outside all zones).

### 7.4 VA vs NVA classification

- For each video, users define which zones are VA for each worker.
- During metric computation, for each frame where a worker is present:
  - If the worker’s centroid is in any zone that is marked VA for that worker, that frame counts as VA.
  - Otherwise, that frame counts as NVA.
- The system sums VA and NVA frames for each worker, then converts to seconds using the video fps:
  - va_seconds = va_frames / fps
  - nva_seconds = nva_frames / fps
  - va_percentage = va_seconds / (va_seconds + nva_seconds) × 100

Metrics are stored in the vava_metrics table and served via analytics endpoints and the Analytics page.

### 7.5 ID merging

Sometimes a worker temporarily leaves the frame or becomes fully occluded, and SORT might assign a new track_id when the person reappears.

- To handle this, the system allows you to define merged worker IDs.
- A merge record lists a merged_worker_id and the original track IDs that belong to that worker.
- When metrics are computed or recomputed after a merge:
  - All frames belonging to any of the original track IDs are grouped under the merged_worker_id.
  - VA/NVA counts and percentages are recomputed for the merged worker.

This ensures that each physical worker can be analyzed as a single entity even if tracking IDs change during the video.

---

## 8. API overview

The backend exposes a REST API under the /api prefix. Below is a condensed overview of the main endpoints so you can quickly integrate or debug.

Base URL (local):

```text
http://localhost:8000/api
```

### 8.1 Videos

- POST /videos/upload
  - multipart/form-data with a "file" field for the video.
  - Creates a video record, extracts metadata, and stores the file and first frame.

- GET /videos
  - Lists all videos with basic metadata and processing status.

- GET /videos/{video_id}
  - Returns full metadata for a specific video.

- GET /videos/{video_id}/first-frame
  - Returns the first frame as an image.

- POST /videos/{video_id}/process
  - Starts detection + tracking for the given video (background task).

- GET /videos/{video_id}/summary
  - High‑level summary including worker IDs and their frame ranges.

- DELETE /videos/{video_id}
  - Deletes the video and associated data.

### 8.2 Zones

- POST /zones
  - Create a zone for a given video by sending a label, polygon, and color.

- GET /videos/{video_id}/zones
  - List all zones for a video.

- PUT /zones/{zone_id}
  - Update label or polygon.

- DELETE /zones/{zone_id}
  - Delete a zone.

### 8.3 Worker–zone mapping

- POST /worker-zones/assign
  - Assign which zones are VA for a given worker.

- GET /videos/{video_id}/worker-zones
  - List all worker–zone assignments for a video.

### 8.4 ID merges

- POST /id-merges
  - Create a merge that maps several track IDs to a single logical worker ID.

- GET /videos/{video_id}/id-merges
  - List all merges for a video.

### 8.5 Analytics

- POST /videos/{video_id}/compute-metrics
  - Compute (or recompute) VA/NVA metrics for the video using current zones, assignments, and merges.

- GET /videos/{video_id}/metrics
  - Get per‑worker VA/NVA metrics.

- GET /videos/{video_id}/worker-timeline/{worker_id}
  - Get a time‑ordered sequence describing where a worker was and whether that position counted as VA.

You can explore all endpoints interactively at http://localhost:8000/docs.

---

## 9. Data model (SQLite)

At a high level, the database contains the following tables:

- videos
  - One row per uploaded video: id, filename, fps, duration_sec, width, height, total_frames, first_frame_path, uploaded_at, status.

- tracks
  - Frame‑level tracking data: video_id, frame_idx, track_id, bounding box coordinates, centroid, confidence.

- zones
  - One row per polygon zone: id, video_id, label, polygon_json, color.

- worker_zone_mapping
  - Mapping of worker_id + zone_id to whether that zone is VA for that worker.

- id_merges
  - Records merges of multiple track IDs into a single merged_worker_id.

- vava_metrics
  - Final per‑worker metrics: va_frames, nva_frames, va_seconds, nva_seconds, va_percentage.

The schema is implemented with SQLAlchemy models in backend/app/db/models.py.

---

## 10. Troubleshooting

Some common issues and fixes:

### 10.1 Backend import errors (e.g., "No module named 'ultralytics'")

Make sure you are in the virtual environment and install dependencies again:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt --upgrade
```

### 10.2 Frontend will not start

```bash
cd frontend
npm install
npm run dev
```

If the port is already in use, stop the other process or change the dev server port in vite.config.js.

### 10.3 Video not processing or failing

- Prefer MP4 with H.264 video codec.
- If you have an older or unusual file format, try re‑encoding with ffmpeg:

```bash
ffmpeg -i input.avi -c:v libx264 -c:a aac output.mp4
```

- Check the backend logs for error messages.

### 10.4 Database locked or corrupted

For local testing only, you can reset the database:

```bash
cd backend
deactivate  # if needed
rm tracking.db  # or delete via Explorer on Windows
```

Then restart the backend; it will recreate the database structure.

### 10.5 SORT seems to lose tracks too often

Tweak the SORT parameters in backend/app/core/ml_pipeline.py or sort.py:
- Increase max_age to keep tracks alive longer when detections are briefly missing.
- Lower the confidence threshold for detections if people are occasionally missed.
- Increase min_hits if you are seeing too many short, noisy tracks.

---

## 11. Extending and hardening the system

This codebase is designed to be easy to extend.

Ideas for extensions:

- Add pose estimation to classify activity types (e.g., lifting, bending).
- Swap SORT for DeepSORT if ID stability in crowded scenes becomes critical.
- Add WebSocket endpoints to stream partial results or live video annotations.
- Add export features (CSV/PDF reports of VA/NVA metrics).
- Add authentication/authorization around the API for production deployments.

For production use, you will likely want to:

- Add a proper logging and monitoring setup.
- Add authentication (e.g., JWT) and role‑based access control.
- Put the backend behind a reverse proxy (nginx, Traefik) and run under process supervision (systemd, Docker, Kubernetes, etc.).
- Add automated tests around critical logic (geometry, metric computation, ID merging).

---

## 12. Getting the repository ready for GitHub

This repository is already structured to be pushed to GitHub:

- A .gitignore file is included to keep build artifacts, virtual environments, node_modules, logs, and local env files out of version control while keeping code and configuration in.
- The model weights file yolov8n.pt is present so the project can run out‑of‑the‑box after clone (you can choose to remove or host this elsewhere if size becomes an issue).

Before pushing, you may want to:

- Add a LICENSE file that matches how you want others to use the code (for example MIT, Apache‑2.0, or a proprietary license).
- Review the README and update the git clone URL and any organization‑specific notes.

After that, you can create a new GitHub repository and push this codebase as‑is.

---

## 13. Summary

This project provides a complete pipeline to turn raw production videos into per‑worker VA/NVA time metrics:

- YOLOv8n detects workers frame‑by‑frame.
- SORT tracks each worker through the video.
- Users draw zones and define which zones count as value‑added work.
- The system computes VA/NVA time per worker, stores results, and visualizes them in a web dashboard.

Use this as a starting point for VA/NVA studies, internal productivity analysis tools, or as a base for more advanced research systems.
