import os, re, requests, tempfile
import numpy as np
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoFileClip, ImageClip, CompositeVideoClip,
    AudioFileClip, concatenate_videoclips
)

WIDTH, HEIGHT = 1080, 1920
TARGET_DURATION = 60  # hard cap for Shorts
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"  # exists on ubuntu-latest

def _pexels_search(query):
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        return []
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": key},
            params={"query": query, "per_page": 5, "orientation": "portrait", "size": "medium"},
            timeout=30
        )
        if r.status_code != 200:
            return []
        items = r.json().get("videos", [])
        urls = []
        for v in items:
            files = v.get("video_files", [])
            files = sorted(files, key=lambda x: x.get("width", 9_999_999))
            if files:
                urls.append(files[0]["link"])
        return urls
    except Exception:
        return []

def _download(url, suffix):
    fp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        for chunk in r.iter_content(1024 * 256):
            fp.write(chunk)
    fp.flush(); fp.close()
    return fp.name

def _get_broll():
    kws = ["robot", "robot arm", "automation", "factory", "ai lab"]
    paths = []
    for kw in kws:
        urls = _pexels_search(kw)
        if urls:
            try:
                paths.append(_download(urls[0], ".mp4"))
            except Exception:
                pass
        if len(paths) >= 2:
            break
    if not paths and os.path.exists("assets/fallback_stock.mp4"):
        paths = ["assets/fallback_stock.mp4"]
    return paths

def _wrap_text(body):
    body = re.sub(r"\s+", " ", (body or "")).strip()
    words = body.split()
    lines, line = [], []
    for w in words:
        line.append(w)
        if len(" ".join(line)) > 34:
            lines.append(" ".join(line)); line = []
    if line:
        lines.append(" ".join(line))
    return lines

def _wrap_text_to_width(draw, text, font, max_width):
    words = text.split()
    lines, line = [], []
    for w in words:
        test = " ".join(line + [w])
        w_px, _ = draw.textsize(test, font=font)
        if w_px <= max_width:
            line.append(w)
        else:
            if line:
                lines.append(" ".join(line))
            line = [w]
    if line:
        lines.append(" ".join(line))
    return lines

def _make_text_clip(text, start, duration, y_ratio=0.14, fontsize=60, max_width=None):
    if max_width is None:
        max_width = WIDTH - 120
    W, H = max_width, 600
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, fontsize)

    lines = _wrap_text_to_width(draw, text, font, max_width=W)
    line_h = int(fontsize * 1.25)
    total_h = line_h * max(1, len(lines))
    y = (H - total_h) // 2

    for ln in lines:
        w_px, _ = draw.textsize(ln, font=font)
        x = (W - w_px) // 2
        # soft shadow
        draw.text((x+2, y+2), ln, font=font, fill=(0, 0, 0, 180))
        draw.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
        y += line_h

    clip = ImageClip(np.array(img)).set_start(start).set_duration(duration)
    return clip.set_position(("center", int(HEIGHT * y_ratio)))

def make_short_video(item, script):
    title = (script.get("title") or item["title"]).strip()
    body = (script.get("body") or item["title"]).strip()
    tag_str = script.get("tags", "robotics, ai, news")
    tags = [t.strip() for t in tag_str.split(",") if t.strip()]

    # B-roll background
    broll_paths = _get_broll()
    if not broll_paths:
        raise RuntimeError("No b-roll available (Pexels key missing and no fallback asset).")

    clips = []
    per_clip = max(8, TARGET_DURATION / max(1, len(broll_paths)))
    for p in broll_paths:
        clip = VideoFileClip(p).resize(height=HEIGHT)
        # center crop to 9:16
        clip = clip.crop(x_center=clip.w / 2, width=WIDTH, height=HEIGHT)
        # trim each to per_clip seconds
        d = min(clip.duration, per_clip)
        clip = clip.set_duration(d)
        clips.append(clip)

    bg = concatenate_videoclips(clips, method="compose")
    total = min(bg.duration, TARGET_DURATION)

    # Captions
    lines = _wrap_text(body)
    per_line = max(0.9, total / max(8, len(lines)))
    txt_clips, t = [], 0.3
    for ln in lines:
        txt_clips.append(_make_text_clip(ln, start=t, duration=per_line, y_ratio=0.14, fontsize=60))
        t += per_line * 0.9

    # CTA footer
    store = os.getenv("STORE_URL", "https://example.com")
    cta = _make_text_clip(f"More at {store}", start=max(0, total - 8), duration=8, y_ratio=0.92, fontsize=40)

    final = CompositeVideoClip([bg] + txt_clips + [cta], size=(WIDTH, HEIGHT)).set_duration(total)

    # Optional background music
    music_path = "assets/music.mp3"
    if os.path.exists(music_path):
        try:
            music = AudioFileClip(music_path).volumex(0.22).set_duration(final.duration)
            final = final.set_audio(music)
        except Exception as e:
            print("Music load failed:", e)

    # Export
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = f"out_{ts}.mp4"
    final.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac",
                          preset="veryfast", threads=2, verbose=False, logger=None)

    # Thumbnail
    thumb_path = f"thumb_{ts}.jpg"
    final.save_frame(thumb_path, t=min(0.5, max(0.1, total / 10.0)))

    description = f"{body}\n\nSource: {item.get('link','')}\n\nMore: {store}"
    return out_path, thumb_path, title, description, tags
