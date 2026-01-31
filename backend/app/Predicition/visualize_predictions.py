import cv2
import json
import os
import numpy as np
from pathlib import Path
from tqdm import tqdm

def draw_text(
    frame, 
    text, 
    position=(10, 30), 
    font_scale=0.8, 
    font_thickness=2,
    text_color=(255, 255, 255),
    bg_color=(0, 0, 0),
    padding=5
):
    """Draw text with background on the frame"""
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size, _ = cv2.getTextSize(text, font, font_scale, font_thickness)
    
    # Draw background rectangle
    cv2.rectangle(
        frame,
        (position[0] - padding, position[1] - text_size[1] - padding),
        (position[0] + text_size[0] + padding, position[1] + padding),
        bg_color,
        -1
    )
    
    # Draw text
    cv2.putText(
        frame, 
        text, 
        position,
        font, 
        font_scale, 
        text_color, 
        font_thickness, 
        cv2.LINE_AA
    )
    return frame

def visualize_predictions(video_path, json_path, output_path):
    """Process video and save with action predictions
    
    Args:
        video_path: Path to input video
        json_path: Path to prediction JSON file
        output_path: Path to save output video
    """
    # Load predictions
    with open(json_path, 'r') as f:
        segments = json.load(f)
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    
    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # No preview window needed
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Create output video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    # Create a color map for different actions
    colors = {
        'get': (0, 255, 0),       # Green
        'collect': (0, 165, 255),  # Orange
        'connect': (255, 0, 0),    # Blue
        'hand': (255, 255, 0),     # Cyan
        'mark': (255, 0, 255),     # Magenta
        'mount': (0, 255, 255),    # Yellow
        'default': (255, 255, 255) # White
    }
    
    frame_idx = 0
    current_segment = None
    
    with tqdm(total=total_frames, desc="Processing video") as pbar:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            current_time = frame_idx / fps
            
            # Find current segment
            for segment in segments:
                if segment['start'] <= current_time <= segment['end']:
                    current_segment = segment
                    break
                else:
                    current_segment = None
            
            # Draw current action
            if current_segment:
                action = current_segment['fine_action']
                action_type = current_segment['coarse_action'].lower()
                color = colors.get(action_type, colors['default'])
                
                # Draw action text
                draw_text(
                    frame, 
                    f"Action: {action}",
                    position=(10, 30),
                    font_scale=0.8,
                    font_thickness=2,
                    text_color=color,
                    bg_color=(0, 0, 0)
                )
                
                # Draw progress bar
                progress = (current_time - current_segment['start']) / (segment['end'] - segment['start'])
                cv2.rectangle(
                    frame,
                    (0, height - 10),
                    (int(width * progress), height),
                    color,
                    -1
                )
            
            # Write frame to output video
            out.write(frame)
            
            # No preview - just process the frame
            
            frame_idx += 1
            pbar.update(1)
    
    # Release resources
    cap.release()
    out.release()
    # No preview windows to close

def process_all_videos():
    """Process all videos in the testing directory without showing preview"""
    """Process all videos in the testing directory"""
    # Base directories
    base_dir = Path(__file__).parent
    testing_dir = base_dir.parent / "testing"
    predictions_dir = base_dir / "predictions"
    output_dir = base_dir / "predictions" / "visualized"
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all video files in testing directory
    video_files = list(testing_dir.glob("*.mp4"))
    
    for video_path in video_files:
        # Get corresponding JSON file
        json_path = predictions_dir / f"{video_path.stem}_results.json"
        
        if not json_path.exists():
            print(f"Warning: No prediction found for {video_path.name}")
            continue
            
        # Set output path
        output_path = output_dir / f"{video_path.stem}_visualized.mp4"
        
        print(f"\nProcessing: {video_path.name}")
        print(f"Using predictions from: {json_path}")
        print(f"Output will be saved to: {output_path}")
        
        try:
            visualize_predictions(str(video_path), str(json_path), str(output_path))
            print(f"✅ Successfully processed {video_path.name}")
        except Exception as e:
            print(f"❌ Error processing {video_path.name}: {str(e)}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Visualize action predictions on video(s)')
    parser.add_argument('--video_path', type=str, help='Path to input video')
    parser.add_argument('--json_path', type=str, help='Path to prediction JSON file')
    parser.add_argument('--output_path', type=str, help='Path to save output video')
    parser.add_argument('--process_all', action='store_true', help='Process all videos in testing directory')
    # Preview functionality removed
    
    args = parser.parse_args()
    
    if args.process_all:
        process_all_videos()  # Process all videos without preview
    elif args.video_path and args.json_path:
        # Set default output path if not provided
        if not args.output_path:
            video_dir = os.path.dirname(args.video_path)
            video_name = os.path.splitext(os.path.basename(args.video_path))[0]
            output_dir = os.path.join(video_dir, "visualized")
            os.makedirs(output_dir, exist_ok=True)
            args.output_path = os.path.join(output_dir, f"{video_name}_visualized.mp4")
        
        print(f"Processing: {args.video_path}")
        print(f"Using predictions from: {args.json_path}")
        print(f"Output will be saved to: {args.output_path}")
        
        visualize_predictions(
            args.video_path, 
            args.json_path, 
            args.output_path,
            preview=False
        )
        print("✅ Visualization complete!")
    else:
        print("Please provide either --process_all or both --video_path and --json_path")
        print("\nExamples:")
        print("  Process single video:")
        print("    python visualize_predictions.py --video_path ../testing/collect_hardware_rnva_002.mp4 --json_path predictions/collect_hardware_rnva_002_results.json")
        print("\n  Process all videos in testing directory:")
        print("    python visualize_predictions.py --process_all")
