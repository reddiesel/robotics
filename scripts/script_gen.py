import os, re, json, requests

SYS_PROMPT = (
    "Write a 70–110 second YouTube Short voiceover about the news item.\n"
    "Audience: curious teens & adults.\n"
    "Style: clear, punchy, 2-sentence hook, then 3–4 crisp points, end with one-sentence takeaway.\n"
    "NO clickbait. Mention the source topic naturally.\n"
    "Return JSON with keys: title, body, tags (comma-separated up to 10)."
)

def _openrouter(prompt: str) -> str:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        # Fallback: simple title/body if no key yet
        return json.dumps({
            "title": "Robotics update",
            "body": f"{prompt}\n(LLM key not set; placeholder script.)",
            "tags": "robotics, ai, technology"
        })
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYS_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 800,
        "temperature": 0.7
    }
    r = requests.post(url, headers=headers, json=data, timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def write_short_script(item: dict) -> dict:
    prompt = f"News headline: {item.get('title','')}\nURL: {item.get('link','')}\nCompose now."
    raw = _openrouter(prompt)
    try:
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            return json.loads(m.group(0))
    except Exception:
        pass
    # Soft fallback if parsing fails
    return {
        "title": item.get("title", "Robotics update"),
        "body": raw if isinstance(raw, str) else "Latest in robotics explained.",
        "tags": "robotics, ai, news"
    }
