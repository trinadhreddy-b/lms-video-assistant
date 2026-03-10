"""
Scene detection and frame extraction using multiple methods
"""

import cv2
import numpy as np
from scenedetect import detect, ContentDetector
from skimage.metrics import structural_similarity as ssim
from config import MAX_SCREENSHOTS_PER_MINUTE


def extract_candidate_frames(video_path, temp_dir):
    """
    Extracts candidate frames using 3 methods.

    Returns: list of frame dicts
    """
    frames_dir = temp_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    # Single OpenCV pass: SSIM + motion detection
    ssim_frames, motion_frames = detect_changes_opencv(video_path, frames_dir)

    # Merge and deduplicate
    all_frames = ssim_frames + motion_frames
    all_frames.sort(key=lambda x: x['timestamp_sec'])

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
    """Method 1: PySceneDetect hard cuts, frames saved via OpenCV."""
    scenes = detect(video_path, ContentDetector(threshold=30.0))
    frames = []
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25

    for scene in scenes:
        ts = scene[0].get_seconds()
        frame_num = int(ts * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, img = cap.read()
        if ret:
            frame_path = frames_dir / f"scene_{ts:.1f}.png"
            cv2.imwrite(str(frame_path), img)
            frames.append({
                'timestamp_sec': ts,
                'timestamp_str': seconds_to_hms(ts),
                'frame_path': str(frame_path),
                'trigger': 'scene_cut'
            })

    cap.release()
    return frames


def detect_changes_opencv(video_path, frames_dir):
    """
    Methods 2 & 3 combined: single OpenCV pass, sampling every 5 seconds.
    Detects SSIM visual changes and motion changes simultaneously.
    """
    ssim_frames = []
    motion_frames = []

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(fps * 5))  # every 5 seconds

    prev_color = None
    prev_gray = None
    frame_num = 0

    total_steps = total_frames // step
    step_count = 0
    print(f"Scanning video for visual changes (0/{total_steps})...", end='\r', flush=True)
    while frame_num < total_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, img = cap.read()
        if not ret:
            break

        ts = frame_num / fps
        step_count += 1
        if step_count % 50 == 0 or step_count == total_steps:
            print(f"Scanning video for visual changes ({step_count}/{total_steps}) — {ts/60:.1f} min processed...", end='\r', flush=True)

        if img is not None and img.shape[0] >= 7 and img.shape[1] >= 7:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # SSIM check
            if prev_color is not None:
                similarity = ssim(prev_color, img, channel_axis=-1)
                if similarity < 0.80:
                    frame_path = frames_dir / f"ssim_{ts:.1f}.png"
                    cv2.imwrite(str(frame_path), img)
                    ssim_frames.append({
                        'timestamp_sec': ts,
                        'timestamp_str': seconds_to_hms(ts),
                        'frame_path': str(frame_path),
                        'trigger': 'visual_change'
                    })

            # Motion check
            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                if np.mean(diff) > 25:
                    frame_path = frames_dir / f"motion_{ts:.1f}.png"
                    if not frame_path.exists():  # avoid duplicate write if ssim already saved
                        cv2.imwrite(str(frame_path), img)
                    motion_frames.append({
                        'timestamp_sec': ts,
                        'timestamp_str': seconds_to_hms(ts),
                        'frame_path': str(frame_path),
                        'trigger': 'ui_interaction'
                    })

            prev_color = img
            prev_gray = gray

        frame_num += step

    cap.release()
    return ssim_frames, motion_frames



def seconds_to_hms(seconds):
    """Convert seconds to HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
