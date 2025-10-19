import feedparser

FEEDS = [
    "https://news.google.com/rss/search?q=robotics+OR+robot+arm+OR+autonomous+robots+when:1d&hl=en-GB&gl=GB&ceid=GB:en",
    "https://www.robotics247.com/rss",
    "https://spectrum.ieee.org/robotics/rss",
]

def get_robotics_items(limit=3):
    entries = []
    for url in FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries[:10]:
            entries.append({
                "title": e.title,
                "link": getattr(e, "link", ""),
            })
    # de-dup & trim
    seen = set()
    uniq = []
    for it in entries:
        t = it["title"].strip()
        if t not in seen:
            seen.add(t)
            uniq.append(it)
        if len(uniq) >= limit:
            break
    return uniq
