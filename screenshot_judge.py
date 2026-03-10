"""
AI-powered screenshot filtering using Claude
"""

import base64
import time
from pathlib import Path
from anthropic import Anthropic
from config import CLAUDE_MODEL, BATCH_SIZE, BATCH_DELAY

def judge_screenshots(candidate_frames, segments):
    """
    Judges candidate frames using Claude AI.

    Returns: list of approved frames
    """
    client = Anthropic()
    approved = []

    for i in range(0, len(candidate_frames), BATCH_SIZE):
        batch = candidate_frames[i:i+BATCH_SIZE]

        for frame in batch:
            try:
                transcript_context = get_transcript_context(frame['timestamp_sec'], segments)

                with open(frame['frame_path'], 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode()

                system_prompt = (
                    "You are an expert educational content analyzer. You review frames captured from lecture "
                    "videos to decide which are worth including in a student's study notes."
                )

                user_prompt = f"""
Timestamp: {frame['timestamp_str']}
Capture reason: {frame['trigger']}
What the instructor is saying: '{transcript_context}'

Should this screenshot be included in study notes?

KEEP if it shows:
- A new slide, diagram, flowchart, or chart
- Code being written, run, or highlighted
- A software UI demonstrating a specific workflow
- Drag-and-drop, clicking, scrolling, typing in a demo
- A terminal or command output
- A key concept, definition, or summary
- Anything the instructor is actively pointing to or explaining

SKIP if it shows:
- Instructor face/webcam with no new visual content behind them
- An unchanged slide already captured recently
- A loading screen or animation frame
- Blurry or motion-blurred content

Respond ONLY in this JSON format:
{{
  'keep': true,
  'reason': 'New slide showing MVC architecture diagram',
  'importance': 'high',
  'category': 'diagram'
}}

Categories: diagram | code | ui-demo | slide | terminal | summary | instructor | other
"""

                response = client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=300,
                    system=system_prompt,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": image_data
                                    }
                                },
                                {
                                    "type": "text",
                                    "value": user_prompt
                                }
                            ]
                        }
                    ]
                )

                result_text = response.content[0].text.strip()
                # Parse JSON (simplified, should use json.loads with error handling)
                import json
                try:
                    result = json.loads(result_text)
                    if result.get('keep'):
                        frame.update(result)
                        approved.append(frame)
                except:
                    # Retry once on bad JSON
                    time.sleep(1)
                    response = client.messages.create(...)  # Same call
                    result_text = response.content[0].text.strip()
                    try:
                        result = json.loads(result_text)
                        if result.get('keep'):
                            frame.update(result)
                            approved.append(frame)
                    except:
                        pass  # Skip on second failure

            except Exception as e:
                print(f"Error judging frame {frame['frame_path']}: {e}")
                continue

        if i + BATCH_SIZE < len(candidate_frames):
            time.sleep(BATCH_DELAY)

    return approved

def get_transcript_context(timestamp, segments, window=15):
    """Get transcript text around timestamp ± window seconds."""
    context = []
    for segment in segments:
        if segment['start'] - window <= timestamp <= segment['end'] + window:
            context.append(segment['text'])
    return ' '.join(context).strip()