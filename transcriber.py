"""
Audio transcription using faster-whisper
"""

from faster_whisper import WhisperModel
import torch
from pathlib import Path
import json
from config import WHISPER_MODEL

def transcribe_audio(audio_path, language="en"):
    """
    Transcribes audio using faster-whisper.

    Returns: list of segments with word-level timestamps
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = WhisperModel(WHISPER_MODEL, device=device)

    segments, info = model.transcribe(audio_path, language=language, word_timestamps=True)

    # Convert to the expected format
    result_segments = []
    for segment in segments:
        words = [{'word': word.word, 'start': word.start, 'end': word.end} for word in segment.words] if segment.words else []
        result_segments.append({
            'start': segment.start,
            'end': segment.end,
            'text': segment.text,
            'words': words
        })

    return result_segments

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