"""
Video Clipper Service
Handles video cutting based on Excel timestamps
"""
import pandas as pd
import os
from moviepy import VideoFileClip
from datetime import time
from pathlib import Path
from typing import Dict, List, Tuple
import json


class VideoClipperService:
    """Service for cutting videos based on Excel timestamps"""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.dataset_dir = storage_dir / "dataset"
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def time_to_seconds(t) -> float:
        """Convert time to seconds"""
        if isinstance(t, time):  # Excel time format
            return t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1000000
        
        t = str(t)
        parts = t.split(":")
        if len(parts) == 3:
            h, m, s = map(float, parts)
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:
            m, s = map(float, parts)
            return m * 60 + s
        else:
            return float(t)
    
    @staticmethod
    def clean_name(name: str) -> str:
        """Clean name for use in folder/file names"""
        name = str(name).lower()
        name = name.replace(" ", "_")
        name = name.replace("-", "_")
        name = name.replace("/", "_")
        name = name.replace("&", "and")
        # Remove any other special characters
        name = "".join(c for c in name if c.isalnum() or c == "_")
        return name
    
    def parse_excel_timestamps(self, excel_path: str) -> pd.DataFrame:
        """Parse Excel file and validate required columns"""
        try:
            df = pd.read_excel(excel_path)
            
            # Check for required columns
            required_columns = ['start_time', 'end_time', 'action_name']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
            
            # VA_RNVA_NVA column is optional
            if 'VA_RNVA_NVA' not in df.columns:
                df['VA_RNVA_NVA'] = 'unknown'
            
            return df
        except Exception as e:
            raise ValueError(f"Error parsing Excel file: {str(e)}")
    
    def cut_video_clips(
        self, 
        video_path: str, 
        excel_path: str, 
        job_id: str,
        progress_callback=None
    ) -> Dict:
        """
        Cut video into clips based on Excel timestamps
        
        Args:
            video_path: Path to input video file
            excel_path: Path to Excel file with timestamps
            job_id: Unique job identifier
            progress_callback: Optional callback function to report progress
        
        Returns:
            Dictionary with job results
        """
        # Parse Excel
        df = self.parse_excel_timestamps(excel_path)
        
        # Get video name without extension
        video_name = Path(video_path).stem
        
        # Create output directory: storage/dataset/{video_name}/
        output_base_dir = self.dataset_dir / video_name
        output_base_dir.mkdir(parents=True, exist_ok=True)
        
        # Load video once
        video = VideoFileClip(video_path)
        
        # Counter per folder
        folder_counter = {}
        clips_info = []
        total_rows = len(df)
        
        try:
            for idx, row in df.iterrows():
                # Convert times to seconds
                start_sec = self.time_to_seconds(row["start_time"])
                end_sec = self.time_to_seconds(row["end_time"])
                
                # Get action name and VA tag
                action = self.clean_name(row["action_name"])
                va_tag = str(row["VA_RNVA_NVA"]).lower()
                
                # File name → action_va / action_rnva / action_nva
                clip_name = f"{action}_{va_tag}"
                
                # Increment counter for this clip type
                folder_counter[clip_name] = folder_counter.get(clip_name, 0) + 1
                count = folder_counter[clip_name]
                
                # Output file directly in video folder (no subfolders)
                output_file = f"{clip_name}_{count:03}.mp4"
                output_path = output_base_dir / output_file

                
                
                # Crop video
                clip = video.subclipped(start_sec, end_sec)
                
                # Try GPU-accelerated encoding first, fallback to CPU if it fails
                try:
                    # GPU-accelerated encoding with NVIDIA NVENC (high quality)
                    clip.write_videofile(
                        str(output_path),
                        codec="h264_nvenc",  # NVIDIA GPU encoder
                        audio=False,
                        logger=None,  # Suppress moviepy output
                        preset="slow",  # Slower = better quality
                        ffmpeg_params=[
                            "-gpu", "0",  # Use first GPU
                            "-rc:v", "vbr",  # Variable bitrate
                            "-cq:v", "18",  # Quality: 18 = very high quality (lower is better)
                            "-b:v", "10M",  # Higher target bitrate for better quality
                            "-maxrate:v", "20M",  # Higher max bitrate
                            "-bufsize:v", "20M"  # Larger buffer
                        ]
                    )
                except Exception as gpu_error:
                    # Fallback to CPU encoding if GPU fails
                    print(f"⚠ GPU encoding failed, using CPU: {gpu_error}")
                    clip.write_videofile(
                        str(output_path),
                        codec="libx264",  # CPU encoder
                        audio=False,
                        logger=None,
                        preset="slow",  # Slower = better quality
                        ffmpeg_params=[
                            "-crf", "18",  # Constant Rate Factor: 18 = very high quality
                        ]
                    )

                
                clip.close()
                
                # Store clip info
                clips_info.append({
                    "filename": output_file,
                    "folder": video_name,  # All clips in video folder
                    "action_name": action,
                    "va_tag": va_tag,
                    "clip_number": count,
                    "duration_sec": end_sec - start_sec,
                    "relative_path": f"{video_name}/{output_file}"  # No subfolder
                })
                
                # Report progress
                if progress_callback:
                    progress = int((idx + 1) / total_rows * 100)
                    progress_callback(progress, idx + 1, total_rows)
                
                print(f"✔ Created: {output_path}")
            
            video.close()
            
            return {
                "status": "complete",
                "total_clips": len(clips_info),
                "clips": clips_info,
                "output_directory": str(output_base_dir)
            }
            
        except Exception as e:
            video.close()
            raise Exception(f"Error cutting video: {str(e)}")
    
    def get_clips_for_job(self, video_name: str) -> List[Dict]:
        """Get list of all clips for a video"""
        output_dir = self.dataset_dir / video_name
        
        if not output_dir.exists():
            return []
        
        clips = []
        # All clips are directly in the video folder (no subfolders)
        for clip_file in output_dir.glob("*.mp4"):
            clips.append({
                "filename": clip_file.name,
                "folder": video_name,
                "relative_path": f"{video_name}/{clip_file.name}",
                "size_bytes": clip_file.stat().st_size
            })
        
        return clips

