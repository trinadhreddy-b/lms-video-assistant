"""
Audio transcription using Groq Whisper API
"""

import os
import time
from pathlib import Path
from groq import Groq, RateLimitError

GROQ_MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB Groq limit

def transcribe_audio(audio_path, language="en"):
    """
    Transcribes audio using Groq's Whisper API.

    Returns: list of segments with word-level timestamps
    """
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    audio_path = Path(audio_path)

    file_size = audio_path.stat().st_size
    if file_size > GROQ_MAX_FILE_BYTES:
        return _transcribe_chunked(client, audio_path, language)

    return _transcribe_file(client, audio_path, language)

def _transcribe_file(client, audio_path, language):
    """Transcribe a single file via Groq API, with rate limit retry."""
    for _ in range(5):
        try:
            with open(audio_path, "rb") as f:
                response = client.audio.transcriptions.create(
                    file=(audio_path.name, f),
                    model="whisper-large-v3",
                    language=language,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )
            return [
                {
                    'start': seg['start'],
                    'end': seg['end'],
                    'text': seg['text'],
                    'words': [],
                }
                for seg in response.segments
            ]
        except RateLimitError as e:
            wait = 70  # default wait
            msg = str(e)
            # Try to parse wait time from error message
            import re
            m = re.search(r'try again in (\d+)m(\d+)s', msg)
            if m:
                wait = int(m.group(1)) * 60 + int(m.group(2)) + 5
            else:
                m = re.search(r'try again in (\d+)s', msg)
                if m:
                    wait = int(m.group(1)) + 5
            print(f"Rate limit hit, waiting {wait}s before retry...")
            time.sleep(wait)
    raise RuntimeError("Exceeded max retries due to rate limiting")

def _transcribe_chunked(client, audio_path, language):
    """Split audio into <25 MB chunks and transcribe each via Groq API."""
    import subprocess
    import tempfile

    print(f"File exceeds 25 MB Groq limit, splitting into chunks...")
    chunk_dir = Path(tempfile.mkdtemp(prefix="groq_chunks_"))
    chunk_pattern = str(chunk_dir / "chunk_%03d.mp3")

    # Split into ~10-minute chunks as mp3 (much smaller than mp4)
    subprocess.run([
        "ffmpeg", "-i", str(audio_path),
        "-f", "segment", "-segment_time", "600",
        "-vn", "-acodec", "libmp3lame", "-q:a", "4",
        chunk_pattern
    ], check=True, capture_output=True)

    chunks = sorted(chunk_dir.glob("chunk_*.mp3"))
    print(f"Split into {len(chunks)} chunks")

    all_segments = []
    time_offset = 0.0

    for i, chunk in enumerate(chunks):
        print(f"Transcribing chunk {i+1}/{len(chunks)}...")
        chunk_segments = _transcribe_file(client, chunk, language)
        for seg in chunk_segments:
            all_segments.append({
                'start': seg['start'] + time_offset,
                'end': seg['end'] + time_offset,
                'text': seg['text'],
                'words': [],
            })
        if chunk_segments:
            time_offset += chunk_segments[-1]['end']

    import shutil
    shutil.rmtree(chunk_dir, ignore_errors=True)
    return all_segments

def parse_youtube_subtitles(vtt_path):
    """
    Parses YouTube VTT subtitles into segment format similar to WhisperX.

    Returns: list of segments
    """
    # This is a simplified parser. Real implementation would handle VTT format properly.
    segments = []
    with open(vtt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse VTT (simplified)
    lines = content.split('\n')
    current_segment = None
    for line in lines:
        if '-->' in line:
            # Timestamp line
            start, end = line.split(' --> ')
            start_sec = vtt_to_seconds(start)
            end_sec = vtt_to_seconds(end)
            current_segment = {
                'start': start_sec,
                'end': end_sec,
                'text': '',
                'words': []
            }
        elif line.strip() and current_segment:
            current_segment['text'] += line.strip() + ' '
        elif line.strip() == '' and current_segment:
            if current_segment['text'].strip():
                segments.append(current_segment)
            current_segment = None

    if current_segment and current_segment['text'].strip():
        segments.append(current_segment)

    return segments

def vtt_to_seconds(timestamp):
    """Convert VTT timestamp to seconds."""
    h, m, s = timestamp.replace(',', '.').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)