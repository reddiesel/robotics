import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def _yt_service():
    creds = Credentials(
        token=None,
        refresh_token=os.getenv("YT_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("YT_CLIENT_ID"),
        client_secret=os.getenv("YT_CLIENT_SECRET"),
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds)

def upload_short(video_path, thumb_path, title, description, tags):
    # If creds missing, just skip upload (lets you test generation first).
    if not (os.getenv("YT_CLIENT_ID") and os.getenv("YT_CLIENT_SECRET") and os.getenv("YT_REFRESH_TOKEN")):
        print("YouTube credentials not set; skipping upload. Video saved locally in the workspace:", video_path)
        return

    yt = _yt_service()
    body = {
        "snippet": {
            "title": title[:95],
            "description": description[:4900],
            "tags": tags,
            "categoryId": "28"  # Science & Technology
        },
        "status": {"privacyStatus": "public"},  # change to "private" while testing
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/*")
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    vid = response.get("id")
    print("Uploaded video id:", vid)

    # thumbnail
    try:
        yt.thumbnails().set(videoId=vid, media_body=thumb_path).execute()
        print("Thumbnail set.")
    except Exception as e:
        print("Thumbnail set failed:", e)
