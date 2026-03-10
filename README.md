# LMS Video Learning Assistant

A Python-based tool that logs into a custom LMS portal, extracts embedded YouTube or Vimeo videos, downloads them, transcribes the audio, selects intelligent screenshots using AI, and produces a Word study document.

## Features

- Browser automation with Playwright for LMS login
- Automatic detection of YouTube/Vimeo embeds
- Video download with yt-dlp
- Audio transcription with WhisperX
- Intelligent screenshot extraction using multiple methods
- AI-powered screenshot filtering with Claude
- Word document generation with transcripts and screenshots

## Installation

1. Install Python 3.11+
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install Playwright browser:
   ```bash
   playwright install chromium
   ```
4. Install ffmpeg (system dependency):
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
   - Windows: Download from https://ffmpeg.org/download.html

## Set API Key

Set your Anthropic API key:
```bash
export ANTHROPIC_API_KEY=your_key_here
```

## Usage

### Basic Usage
```bash
python main.py \
  --lms-url https://learn.myportal.com \
  --video-page https://learn.myportal.com/courses/5/lessons/12 \
  --output lecture_notes
```

### Fast Mode (YouTube videos with captions)
```bash
python main.py --lms-url ... --video-page ... --skip-whisper
```

### Debug Browser
```bash
python main.py ... --headless false
```

### Dry Run (just get video URL)
```bash
python main.py ... --dry-run
```

## CLI Arguments

- `--lms-url`: Base LMS URL
- `--video-page`: Full URL of the video lesson page
- `--username`: LMS username (prompted securely if omitted)
- `--password`: LMS password (prompted securely if omitted)
- `--output`: Output filename (default: study_notes)
- `--language`: Transcription language (default: en)
- `--headless`: Run browser in headless mode (default: True)
- `--skip-whisper`: Use YouTube captions instead of WhisperX (faster)
- `--dry-run`: Login + extract video URL only, print it, stop
- `--save-credentials`: Save credentials to OS keychain
- `--use-saved-credentials`: Load credentials from keychain

## Project Structure

```
lms-video-assistant/
├── main.py
├── config.py
├── browser_session.py
├── video_downloader.py
├── transcriber.py
├── scene_detector.py
├── screenshot_judge.py
├── document_builder.py
├── utils.py
├── requirements.txt
└── README.md
```

## Security

- Passwords are never logged or printed
- Credentials can be stored securely in OS keychain using keyring
- API keys from environment variables only
- Temporary files cleaned up automatically