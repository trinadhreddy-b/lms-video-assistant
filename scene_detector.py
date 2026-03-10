"""
Scene detection and frame extraction using multiple methods
"""

import cv2
import numpy as np
from scenedetect import detect, ContentDetector
from skimage.metrics import structural_similarity as ssim
from pathlib import Path
import subprocess
from config import MAX_SCREENSHOTS_PER_MINUTE

def extract_candidate_frames(video_path, temp_dir):
    """
    Extracts candidate frames using 3 methods.

    Returns: list of frame dicts
    """
    frames_dir = temp_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    # Get video duration
    duration = get_video_duration(video_path)

    # Method 1: PySceneDetect
    scene_frames = detect_scenes(video_path, frames_dir)

    # Method 2: SSIM change detection
    ssim_frames = detect_ssim_changes(video_path, frames_dir, duration)

    # Method 3: Optical flow / motion detection
    motion_frames = detect_motion(video_path, frames_dir, duration)

    # Merge and deduplicate
    all_frames = scene_frames + ssim_frames + motion_frames
    all_frames.sort(key=lambda x: x['timestamp_sec'])

    # Remove duplicates within 2 seconds
    deduped = []
    last_ts = -10
    for frame in all_frames:
        if frame['timestamp_sec'] - last_ts >= 2:
            deduped.append(frame)
            last_ts = frame['timestamp_sec']

    # Cap per minute
    capped = []
    minute_frames = {}
    for frame in deduped:
        minute = int(frame['timestamp_sec'] // 60)
        if minute not in minute_frames:
            minute_frames[minute] = []
        if len(minute_frames[minute]) < MAX_SCREENSHOTS_PER_MINUTE:
            minute_frames[minute].append(frame)
            capped.append(frame)

    return capped

def detect_scenes(video_path, frames_dir):
    """Method 1: PySceneDetect hard cuts."""
    scenes = detect(video_path, ContentDetector(threshold=30.0))
    frames = []
    for scene in scenes:
        ts = scene[0].get_seconds()
        frame_path = extract_frame_at_time(video_path, ts, frames_dir, f"scene_{ts:.1f}")
        frames.append({
            'timestamp_sec': ts,
            'timestamp_str': seconds_to_hms(ts),
            'frame_path': str(frame_path),
            'trigger': 'scene_cut'
        })
    return frames

def detect_ssim_changes(video_path, frames_dir, duration):
    """Method 2: SSIM change detection every 5 seconds."""
    frames = []
    prev_frame = None
    for ts in np.arange(0, duration, 5):
        frame = extract_frame_at_time(video_path, ts, frames_dir, f"temp_{ts:.1f}")
        if frame.exists():
            img = cv2.imread(str(frame))
            if prev_frame is not None:
                similarity = ssim(prev_frame, img, multichannel=True)
                if similarity < 0.80:
                    frame_path = extract_frame_at_time(video_path, ts, frames_dir, f"ssim_{ts:.1f}")
                    frames.append({
                        'timestamp_sec': ts,
                        'timestamp_str': seconds_to_hms(ts),
                        'frame_path': str(frame_path),
                        'trigger': 'visual_change'
                    })
            prev_frame = img
        frame.unlink(missing_ok=True)  # Remove temp frame
    return frames

def detect_motion(video_path, frames_dir, duration):
    """Method 3: Optical flow / motion detection."""
    frames = []
    prev_frame = None
    for ts in np.arange(0, duration, 5):
        frame = extract_frame_at_time(video_path, ts, frames_dir, f"temp_{ts:.1f}")
        if frame.exists():
            img = cv2.imread(str(frame))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if prev_frame is not None:
                diff = cv2.absdiff(prev_frame, gray)
                mean_diff = np.mean(diff)
                if mean_diff > 25:
                    frame_path = extract_frame_at_time(video_path, ts, frames_dir, f"motion_{ts:.1f}")
                    frames.append({
                        'timestamp_sec': ts,
                        'timestamp_str': seconds_to_hms(ts),
                        'frame_path': str(frame_path),
                        'trigger': 'ui_interaction'
                    })
            prev_frame = gray
        frame.unlink(missing_ok=True)
    return frames

def extract_frame_at_time(video_path, ts, frames_dir, prefix):
    """Extract frame at specific timestamp."""
    output_path = frames_dir / f"{prefix}.png"
    cmd = [
        'ffmpeg', '-ss', str(ts), '-i', str(video_path),
        '-frames:v', '1', '-q:v', '2', str(output_path), '-y'
    ]
    subprocess.run(cmd, capture_output=True)
    return output_path

def get_video_duration(video_path):
    """Get video duration in seconds."""
    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', str(video_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return float(data['format']['duration'])

def seconds_to_hms(seconds):
    """Convert seconds to HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"