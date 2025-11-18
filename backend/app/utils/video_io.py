"""Video I/O helper utilities."""
import cv2
from typing import Tuple


def open_video(path: str):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError("Cannot open video")
    return cap


def read_frame(cap, index: int):
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = cap.read()
    if not ok:
        return None
    return frame


def video_metadata(path: str) -> Tuple[float, int, float]:
    cap = open_video(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_seconds = frame_count / fps if fps else 0.0
    cap.release()
    return fps, frame_count, duration_seconds
