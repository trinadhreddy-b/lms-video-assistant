"""
Video downloader using yt-dlp
"""

import yt_dlp
from pathlib import Path
from config import VIDEO_FORMAT_YOUTUBE, VIDEO_FORMAT_VIMEO

def download_video(video_info, temp_dir):
    """
    Downloads video using yt-dlp.

    video_info: dict from get_embed_video_url
    temp_dir: Path to temp directory

    Returns: {"video_path": str, "subtitles_path": str or None}
    """
    platform = video_info["platform"]
    video_url = video_info["video_url"]
    page_url = video_info["page_url"]
    cookies_file = video_info.get("cookies_file")

    output_path = temp_dir / "video.%(ext)s"

    if platform == "youtube":
        ydl_opts = {
            'outtmpl': str(output_path),
            'format': VIDEO_FORMAT_YOUTUBE,
            'merge_output_format': 'mp4',
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'quiet': False,
        }
    elif platform == "vimeo":
        ydl_opts = {
            'outtmpl': str(output_path),
            'format': VIDEO_FORMAT_VIMEO,
            'merge_output_format': 'mp4',
            # Referer must be the LMS page for private/unlisted Vimeo embeds
            'http_headers': {
                'Referer': page_url,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
            'quiet': False,
        }
        # Only pass cookies if the file exists and has actual cookie entries
        if cookies_file and Path(cookies_file).exists():
            content = Path(cookies_file).read_text()
            if any(line.strip() and not line.startswith('#') for line in content.splitlines()):
                ydl_opts['cookiefile'] = cookies_file
    else:
        raise ValueError(f"Unsupported platform: {platform}")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    # Find the downloaded video file
    video_files = list(temp_dir.glob("video.*"))
    if not video_files:
        raise FileNotFoundError("Video file not found after download")

    video_path = video_files[0]

    # Check for subtitles
    subtitles_path = None
    if platform == "youtube":
        sub_files = list(temp_dir.glob("video.en.*"))
        if sub_files:
            subtitles_path = str(sub_files[0])

    return {
        "video_path": str(video_path),
        "subtitles_path": subtitles_path
    }