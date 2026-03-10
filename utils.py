"""
Utility functions
"""

def format_timestamp(seconds):
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def safe_filename(name):
    """Make string safe for filename."""
    return "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()