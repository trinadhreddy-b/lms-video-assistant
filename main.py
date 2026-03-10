#!/usr/bin/env python3
"""
LMS Video Learning Assistant - Main CLI
"""

import argparse
import getpass
import sys
import os
from pathlib import Path
import keyring
import tempfile
import shutil
# from rich.console import Console
# from rich.progress import Progress, SpinnerColumn, TextColumn

from config import *
from browser_session import get_embed_video_url
from video_downloader import download_video
from transcriber import transcribe_audio, parse_youtube_subtitles
from scene_detector import extract_candidate_frames
from screenshot_judge import judge_screenshots
from document_builder import build_document

# console = Console()

def get_credentials(args):
    """Get username and password, either from args, keyring, or prompt."""
    username = args.username
    password = args.password

    if args.use_saved_credentials:
        if not username:
            username = keyring.get_password("lms-assistant", "username")
        if not password:
            password = keyring.get_password("lms-assistant", "password")

    if not username:
        username = input("LMS Username: ")
    if not password:
        password = getpass.getpass("LMS Password: ")

    if args.save_credentials:
        keyring.set_password("lms-assistant", "username", username)
        keyring.set_password("lms-assistant", "password", password)

    return username, password

def main():
    parser = argparse.ArgumentParser(description="LMS Video Learning Assistant")
    parser.add_argument("--lms-url", required=True, help="Base LMS URL")
    parser.add_argument("--video-page", required=True, help="URL of the course listing or video page")
    parser.add_argument("--course-name", default=None, help="Course name to select on the listing page (partial match)")
    parser.add_argument("--video-title", default=None, help="Video title to select from the session list (partial match)")
    parser.add_argument("--username", help="LMS username")
    parser.add_argument("--password", help="LMS password")
    parser.add_argument("--output", default="study_notes", help="Output filename (without .docx)")
    parser.add_argument("--language", default="en", help="Transcription language")
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True, help="Run browser headless (use --no-headless to show browser window)")
    parser.add_argument("--skip-whisper", action="store_true", help="Use YouTube captions instead of WhisperX")
    parser.add_argument("--dry-run", action="store_true", help="Login + extract video URL only")
    parser.add_argument("--save-credentials", action="store_true", help="Save credentials to keychain")
    parser.add_argument("--use-saved-credentials", action="store_true", help="Load credentials from keychain")

    args = parser.parse_args()

    # Check API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    # Get credentials
    try:
        username, password = get_credentials(args)
    except Exception as e:
        print(f"Error getting credentials: {e}")
        sys.exit(1)

    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp(prefix="lms_assistant_"))
    print(f"Using temp directory: {temp_dir}")

    try:
        # with Progress(
        #     SpinnerColumn(),
        #     TextColumn("[progress.description]{task.description}"),
        #     console=console,
        # ) as progress:
            # Step 1: Login and extract video URL
            # task = progress.add_task("Logging in and extracting video URL...", total=None)
            print("Logging in and extracting video URL...")
            try:
                video_info = get_embed_video_url(
                    args.lms_url, args.video_page, username, password, args.headless,
                    course_name=args.course_name, video_title=args.video_title
                )
                # progress.update(task, completed=True, description="Login and URL extraction complete")
                print("Login and URL extraction complete")
            except Exception as e:
                # progress.update(task, completed=True, description=f"Failed: {e}")
                print(f"Failed: {e}")
                raise

            print(f"Platform: {video_info['platform']}")
            print(f"Video URL: {video_info['video_url']}")

            if args.dry_run:
                return

            # Step 2: Download video
            # task = progress.add_task("Downloading video...", total=None)
            print("Downloading video...")
            try:
                download_result = download_video(video_info, temp_dir)
                # progress.update(task, completed=True, description="Video download complete")
                print("Video download complete")
            except Exception as e:
                # progress.update(task, completed=True, description=f"Failed: {e}")
                print(f"Failed: {e}")
                raise

            video_path = download_result["video_path"]
            subtitles_path = download_result.get("subtitles_path")

            # Step 3: Transcribe
            # task = progress.add_task("Transcribing audio...", total=None)
            print("Transcribing audio...")
            if args.skip_whisper and subtitles_path:
                segments = parse_youtube_subtitles(subtitles_path)
                print("Using YouTube captions for transcript")
            else:
                segments = transcribe_audio(video_path, args.language)
            # progress.update(task, completed=True, description="Transcription complete")
            print("Transcription complete")

            # Step 4: Extract candidate frames
            # task = progress.add_task("Extracting candidate screenshots...", total=None)
            print("Extracting candidate screenshots...")
            candidate_frames = extract_candidate_frames(video_path, temp_dir)
            # progress.update(task, completed=True, description=f"Extracted {len(candidate_frames)} candidate frames")
            print(f"Extracted {len(candidate_frames)} candidate frames")

            # Step 5: Judge screenshots with AI
            # task = progress.add_task("AI filtering screenshots...", total=None)
            print("AI filtering screenshots...")
            approved_frames = judge_screenshots(candidate_frames, segments)
            # progress.update(task, completed=True, description=f"Approved {len(approved_frames)} screenshots")
            print(f"Approved {len(approved_frames)} screenshots")

            # Step 6: Build document
            # task = progress.add_task("Building Word document...", total=None)
            print("Building Word document...")
            output_path = build_document(
                video_info, segments, approved_frames, args.output, temp_dir
            )
            # progress.update(task, completed=True, description="Document built")
            print("Document built")

            # Final summary
            print("\nProcessing complete!")
            print(f"Output: {output_path}")
            print(f"Transcript segments: {len(segments)}")
            print(f"Candidate frames: {len(candidate_frames)}")
            print(f"Approved screenshots: {len(approved_frames)}")

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()