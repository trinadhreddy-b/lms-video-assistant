"""
Browser session management for LMS login and video URL extraction
"""

import re
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

class LoginFailedException(Exception):
    pass

class VideoNotFoundException(Exception):
    pass

def get_embed_video_url(
    lms_url, video_page_url, username, password,
    headless=True, course_name=None, video_title=None
):
    """
    Logs into LMS, navigates to the video, and extracts the embedded video URL.

    Navigation flow (Intellipaat):
      1. Login at lms_url
      2. Go to video_page_url (course listing or direct video page)
      3. If course listing: click "Continue Course" for course_name (or first course)
      4. Click "LIVE CLASSES" tab
      5. Click the video matching video_title (or first video)
      6. Extract video URL via network interception + HTML scanning

    Returns: {
        "platform": "youtube" or "vimeo",
        "video_url": "https://...",
        "page_url": video_page_url,
        "cookies_file": "temp/cookies.txt" or None
    }
    """
    # Network interception captures requests made by dynamic players (blob URLs etc.)
    captured = {"platform": None, "video_id": None, "embed_url": None}

    def handle_request(request):
        url = request.url
        if not captured["video_id"]:
            # Capture full player URL (preserves ?h=HASH token for private videos)
            # Only match the base player URL, not sub-paths like /config /texttracks
            m = re.match(r'https://player\.vimeo\.com/video/(\d+)(\?[^#]*)?', url)
            if m:
                captured["platform"] = "vimeo"
                captured["video_id"] = m.group(1)
                captured["embed_url"] = f"https://player.vimeo.com/video/{m.group(1)}{m.group(2) or ''}"
                return

            yt = re.search(r'youtube(?:-nocookie)?\.com/embed/([a-zA-Z0-9_-]{11})', url)
            if yt:
                captured["platform"] = "youtube"
                captured["video_id"] = yt.group(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        page.on("request", handle_request)

        try:
            # --- Step 1: Login ---
            page.goto(lms_url)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)

            username_field = page.query_selector('input[placeholder="Username"]')
            password_field = page.query_selector('input[placeholder="Password"]')

            if not username_field:
                for selector in ['input[type="text"]', 'input[name*="user"]', 'input[name*="username"]']:
                    username_field = page.query_selector(selector)
                    if username_field:
                        break

            if not password_field:
                for selector in ['input[type="password"]', 'input[name*="pass"]']:
                    password_field = page.query_selector(selector)
                    if password_field:
                        break

            submit_button = page.query_selector('button[type="submit"]') or page.query_selector('button')

            if not username_field or not password_field:
                debug_path = Path(tempfile.gettempdir()) / "debug_form.png"
                page.screenshot(path=str(debug_path))
                raise LoginFailedException(f"Login form not found. Screenshot: {debug_path}")

            username_field.fill(username, force=True)
            page.wait_for_timeout(300)
            password_field.fill(password, force=True)
            page.wait_for_timeout(300)

            if submit_button:
                submit_button.click()
            else:
                password_field.press("Enter")

            page.wait_for_load_state("networkidle")

            # Check login success
            logout_selectors = [
                'a[href*="logout"]', 'a[href*="sign-out"]',
                'a:contains("Logout")', 'a:contains("Sign Out")'
            ]
            logged_in = any(page.query_selector(sel) for sel in logout_selectors)

            if not logged_in and page.url == lms_url:
                debug_path = Path(tempfile.gettempdir()) / "debug_login_fail.png"
                page.screenshot(path=str(debug_path))
                raise LoginFailedException(f"Login failed. Debug screenshot saved to {debug_path}")

            # --- Step 2: Navigate to video_page_url ---
            page.goto(video_page_url)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)

            # --- Step 3: If on course listing page, click "Continue Course" / "Continue" ---
            btn = _find_course_button(page, course_name)
            if btn:
                print(f"Clicking Continue button{' for: ' + course_name if course_name else ''}...")
                btn.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(3000)
                print(f"Now on: {page.url}")
            else:
                print("No Continue button found — assuming already on video page.")

            # --- Step 4: Click "LIVE CLASSES" tab (sidebar icon, any element type) ---
            live_classes_tab = _find_live_classes_tab(page)
            if live_classes_tab:
                print("Clicking LIVE CLASSES tab...")
                live_classes_tab.scroll_into_view_if_needed()
                live_classes_tab.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2000)
            else:
                print("LIVE CLASSES tab not found — may already be visible.")

            # --- Step 5: Select the video from the list ---
            video_item = _find_video_item(page, video_title)
            if video_item:
                print(f"Selecting video{': ' + video_title if video_title else ' (first available)'}...")
                video_item.scroll_into_view_if_needed()
                video_item.click(force=True)
                page.wait_for_load_state("networkidle")
                # Wait for dynamic player to init and fire network requests
                page.wait_for_timeout(5000)
            else:
                # Already on the video page or player auto-loaded
                page.wait_for_timeout(5000)

            # --- Step 6: Detect video URL ---
            platform = captured.get("platform")
            video_id = captured.get("video_id")
            embed_url = captured.get("embed_url")

            if not video_id:
                platform, video_id, embed_url = _scan_iframes(page)

            if not video_id:
                platform, video_id = _scan_page_source(page)

            if not video_id:
                debug_path = Path(tempfile.gettempdir()) / "debug_no_video_found.png"
                page.screenshot(path=str(debug_path))
                iframes = page.query_selector_all("iframe")
                iframe_srcs = [f.get_attribute("src") for f in iframes if f.get_attribute("src")]
                raise VideoNotFoundException(
                    f"Could not find a YouTube or Vimeo embed on this page. "
                    f"Debug screenshot saved to {debug_path}. "
                    f"Iframes found: {iframe_srcs}. "
                    f"Try running with --headless false to inspect the page manually."
                )

            if platform == "vimeo":
                # Use full embed URL to preserve ?h=HASH for private/unlisted videos
                video_url = embed_url or f"https://player.vimeo.com/video/{video_id}"
            else:
                video_url = f"https://www.youtube.com/watch?v={video_id}"

            cookies_file = Path(tempfile.gettempdir()) / "cookies.txt"
            _export_netscape_cookies(context.cookies(), cookies_file)

            return {
                "platform": platform,
                "video_url": video_url,
                "page_url": page.url,
                "cookies_file": str(cookies_file) if platform == "vimeo" else None
            }

        finally:
            browser.close()


def _export_netscape_cookies(cookies, path):
    """Write Playwright cookies to a Netscape-format cookies.txt for yt-dlp."""
    lines = ["# Netscape HTTP Cookie File\n"]
    for c in cookies:
        domain = c.get("domain", "")
        # Netscape format: leading dot means include_subdomains = TRUE
        include_sub = "TRUE" if domain.startswith(".") else "FALSE"
        path_ = c.get("path", "/")
        secure = "TRUE" if c.get("secure") else "FALSE"
        expires = int(c.get("expires", 0))
        if expires < 0:
            expires = 0
        name = c.get("name", "")
        value = c.get("value", "")
        lines.append(f"{domain}\t{include_sub}\t{path_}\t{secure}\t{expires}\t{name}\t{value}\n")
    with open(path, 'w') as f:
        f.writelines(lines)


def _find_live_classes_tab(page):
    """
    Find the LIVE CLASSES sidebar tab on the start-course page.
    It's rendered as a small icon+label div, so we look for the smallest
    element whose exact text is just the label (not a large container div).
    """
    for text in ["LIVE CLASSES", "Live Classes", "LIVE CLASS", "Live Class"]:
        # Prefer a/button first
        for sel in [f'a:has-text("{text}")', f'button:has-text("{text}")', f'li:has-text("{text}")']:
            el = page.query_selector(sel)
            if el:
                return el
        # Fall back to any element — pick the one with the shortest inner text
        # to avoid matching a large parent container
        candidates = page.query_selector_all(f'*:has-text("{text}")')
        best = None
        best_len = float('inf')
        for el in candidates:
            try:
                t = (el.inner_text() or "").strip()
                if text.lower() in t.lower() and len(t) < best_len:
                    best_len = len(t)
                    best = el
            except Exception:
                continue
        if best:
            return best
    return None


def _find_course_button(page, course_name):
    """Find the Continue / Continue Course button for the given course name (or first if none given)."""
    # Button text variants used by Intellipaat LMS
    btn_texts = ["Continue Course", "Continue", "Start Course", "Start"]

    if not course_name:
        for text in btn_texts:
            btn = page.query_selector(f'a:has-text("{text}"), button:has-text("{text}")')
            if btn:
                return btn
        return None

    # Find a card that contains the course name, then get its button
    course_name_lower = course_name.lower()
    for card in page.query_selector_all('div, li, article, section'):
        try:
            text = (card.inner_text() or "").lower()
            if course_name_lower in text:
                for btn_text in btn_texts:
                    btn = card.query_selector(f'a:has-text("{btn_text}"), button:has-text("{btn_text}")')
                    if btn:
                        return btn
        except Exception:
            continue

    # Fallback: first matching button anywhere on page
    for text in btn_texts:
        btn = page.query_selector(f'a:has-text("{text}"), button:has-text("{text}")')
        if btn:
            return btn
    return None


def _find_video_item(page, video_title):
    """Find a video entry in the session list by title (or first available)."""
    # Look for the Online Session Recordings list items
    if video_title:
        # Try to find by title text
        for el in page.query_selector_all('li, a, div[role="button"], div[class*="lesson"], div[class*="unit"]'):
            try:
                text = (el.inner_text() or "").strip()
                if video_title.lower() in text.lower():
                    return el
            except Exception:
                continue

    # Fallback: find the first session recording entry (not already playing)
    # Look for items inside the recording list that are not the current active one
    for el in page.query_selector_all('li, a'):
        try:
            text = (el.inner_text() or "").strip()
            # Session recordings usually have a date pattern like DD/MM/YYYY
            if re.search(r'\d{2}/\d{2}/\d{4}', text) and el.is_visible():
                return el
        except Exception:
            continue

    return None


def _scan_iframes(page):
    """Scan iframe src attributes and content frame URLs for video embeds.
    Returns (platform, video_id, embed_url) where embed_url preserves hash tokens."""
    for iframe_el in page.query_selector_all("iframe"):
        src = iframe_el.get_attribute("src") or ""
        platform, video_id = _match_video_url(src)
        if video_id:
            return platform, video_id, src if platform == "vimeo" else None

        try:
            frame = iframe_el.content_frame()
            if frame and frame.url:
                platform, video_id = _match_video_url(frame.url)
                if video_id:
                    return platform, video_id, frame.url if platform == "vimeo" else None
        except Exception:
            pass

    return None, None, None


def _scan_page_source(page):
    """Scan raw HTML source for video embed patterns."""
    content = page.content()

    yt_match = re.search(r'youtube(?:-nocookie)?\.com/embed/([a-zA-Z0-9_-]{11})', content)
    if yt_match:
        return "youtube", yt_match.group(1)

    vimeo_match = re.search(r'player\.vimeo\.com/video/(\d+)', content) or \
                  re.search(r'"video_id"\s*:\s*"?(\d+)"?', content) or \
                  re.search(r'vimeo\.com/(\d+)', content)
    if vimeo_match:
        return "vimeo", vimeo_match.group(1)

    return None, None


def _match_video_url(url):
    """Return (platform, video_id) from a URL string, or (None, None)."""
    yt = re.search(r'youtube(?:-nocookie)?\.com/embed/([a-zA-Z0-9_-]{11})', url)
    if yt:
        return "youtube", yt.group(1)

    vimeo = re.search(r'player\.vimeo\.com/video/(\d+)', url) or \
            re.search(r'vimeo\.com/(\d+)', url)
    if vimeo:
        return "vimeo", vimeo.group(1)

    return None, None


# Keep detect_embed for backwards compatibility
def detect_embed(page):
    """Detect YouTube or Vimeo embed and return platform and clean URL."""
    platform, video_id, embed_url = _scan_iframes(page)
    if not video_id:
        platform, video_id = _scan_page_source(page)
        embed_url = None
    if not video_id:
        return None, None
    if platform == "vimeo":
        url = embed_url or f"https://player.vimeo.com/video/{video_id}"
    else:
        url = f"https://www.youtube.com/watch?v={video_id}"
    return platform, url
