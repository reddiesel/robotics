import os, re, requests, tempfile
os.environ["IMAGEMAGICK_BINARY"] = "convert"  # use v6 binary name on Ubuntu runners

from datetime import datetime
from moviepy.editor import (
    VideoFileClip, TextClip, CompositeVideoClip,
    AudioFileClip, concatenate_videoclips
)

WIDTH, HEIGHT = 1080, 1920
TARGET_DURATION = 75  # seconds (YouTube Shorts max 60, but we’ll trim if needed)

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
    if not paths:
        if os.path.exists("assets/fallback_stock.mp4"):
            paths = ["assets/fallback_stock.mp4"]
    return paths

def _wrap_text(body):
    body = re.sub(r"\s+", " ", (body or "")).strip()
    words = body.split()
    lines, line = [], []
    for w in words:
        line.append(w)
        if len(" ".join(line)) > 34:
            lines.append(" ".join(line))
            line = []
    if line:
        lines.append(" ".join(line))
    return lines

def make_short_video(item, script):
    title = (script.get("title") or item["title"]).strip()
    body = (script.get("body") or item["title"]).strip()
    tag_str = script.get("tags", "robotics, ai, news")
    tags = [t.strip() for t in tag_str.split(",") if t.strip()]

    # B-roll
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
    total = min(bg.duration, 60)  # keep within Shorts 60s hard cap

    # Caption lines
    lines = _wrap_text(body)
    # Spread captions over total duration
    per_line = max(0.9, total / max(8, len(lines)))
    txt_clips = []
    t = 0.3
    for ln in lines:
        tc = TextClip(
            ln, fontsize=60, font="DejaVu-Sans",
            color="white", method="caption", align="center",
            size=(WIDTH - 120, None)
        )
        tc = tc.set_position(("center", HEIGHT * 0.14)).set_start(t).set_duration(per_line)
        txt_clips.append(tc)
        t += per_line * 0.9

    # CTA footer
    store = os.getenv("STORE_URL", "https://example.com")
    cta = TextClip(
        f"More at {store}",
        fontsize=40, font="DejaVu-Sans", color="white",
        method="caption", align="center", size=(WIDTH - 120, None)
    ).set_position(("center", HEIGHT * 0.92)).set_start(max(0, total - 8)).set_duration(8)

    final = CompositeVideoClip([bg] + txt_clips + [cta], size=(WIDTH, HEIGHT)).set_duration(total)

    # Optional background music
    music_path = "assets/music.mp3"
    if os.path.exists(music_path):
        try:
            music = AudioFileClip(music_path).volumex(0.22).set_duration(final.duration)
            final = final.set_audio(music)
        except Exception as e:
            print("Music load failed:", e)

    # Export files
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = f"out_{ts}.mp4"
    final.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac", preset="veryfast", threads=2, verbose=False, logger=None)

    # Thumbnail from first half-second
    thumb_path = f"thumb_{ts}.jpg"
    final.save_frame(thumb_path, t=min(0.5, max(0.1, total / 10.0)))

    description = f"{body}\n\nSource: {item.get('link','')}\n\nMore: {store}"
    return out_path, thumb_path, title, description, tags
