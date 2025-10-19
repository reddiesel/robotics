import os, time
from scripts.trends import get_robotics_items
from scripts.script_gen import write_short_script
from scripts.video_gen import make_short_video
from scripts.upload import upload_short

def main():
    # 1) find topics
    items = get_robotics_items(limit=1)
    if not items:
        print("No items found."); return

    for i, item in enumerate(items, start=1):
        print(f"\n=== VIDEO {i}/{len(items)}: {item['title']} ===")
        script = write_short_script(item)
        out_path, thumb_path, title, description, tags = make_short_video(item, script)
        upload_short(out_path, thumb_path, title, description, tags)
        # polite pause to avoid API spikes
        time.sleep(5)

if __name__ == "__main__":
    main()
