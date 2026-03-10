"""
Configuration constants for LMS Video Assistant
"""

# Scene detection
MAX_SCREENSHOTS_PER_MINUTE = 6  # Cap on screenshots per minute

# Screenshot judging
CLAUDE_MODEL = "claude-sonnet-4-20250514"
BATCH_SIZE = 5  # Process frames in batches
BATCH_DELAY = 1  # Seconds between batches

# Video download
VIDEO_FORMAT_YOUTUBE = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
VIDEO_FORMAT_VIMEO = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'

# Transcription
WHISPER_MODEL = "large-v3"

# Document building
SECTION_DURATION = 120  # 2 minutes per section
MAX_IMAGE_WIDTH_CM = 14

# Temp directory
TEMP_DIR_PREFIX = "lms_assistant_"