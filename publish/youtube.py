import json
import time
from pathlib import Path

from clipper import config
from publish import rights


def youtube_body(meta: dict, *, public: bool) -> dict:
    """Map a clip's meta.json dict to a YouTube videos.insert request body.
    Appends #Shorts so the 9:16 <60s clip is filed as a Short automatically."""
    hashtags = meta.get("hashtags", [])
    tags = [h.lstrip("#") for h in hashtags]
    desc_tail = " ".join(hashtags + ["#Shorts"])
    description = f"{meta.get('caption', '')}\n\n{desc_tail}".strip()
    return {
        "snippet": {
            "title": meta["title"],
            "description": description,
            "tags": tags,
            "categoryId": config.YT_CATEGORY,
        },
        "status": {
            "privacyStatus": "public" if public else "private",
        },
    }


def log_upload(record: dict, *, ledger: Path = None) -> dict:
    """Append one upload record to logs/uploads.jsonl (local record + daily-quota
    tally + Stage-3 seed)."""
    ledger = ledger or config.UPLOAD_LOG
    rec = {"ts": time.time(), **record}
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def _insert(service, body: dict, video_path: Path) -> dict:
    """Execute the videos.insert call. Imports the Google media helper lazily so
    the pure functions and upload() (with an injected fake) need no Google libs."""
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(str(video_path), mimetype="video/*")
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)
    return request.execute()


def upload(clip_dir, *, public=False, service=None, sources_md=None, ledger=None) -> str:
    """Rights-gate, then upload one clip directory's mp4 to YouTube. Returns the
    watch URL. `service` is injectable for tests; None triggers real OAuth."""
    clip_dir = Path(clip_dir)
    meta = json.loads((clip_dir / "meta.json").read_text())
    rights.check_rights(meta["source"], sources_md=sources_md)  # raises RightsError if not allowed

    video_path = clip_dir / f"{clip_dir.name}.mp4"
    if not video_path.exists():
        mp4s = sorted(clip_dir.glob("*.mp4"))
        if not mp4s:
            raise FileNotFoundError(f"No .mp4 found in {clip_dir}")
        video_path = mp4s[0]

    if service is None:
        service = get_service()

    body = youtube_body(meta, public=public)
    response = _insert(service, body, video_path)
    video_id = response["id"]
    log_upload(
        {
            "source": meta["source"],
            "clip_dir": str(clip_dir),
            "video_id": video_id,
            "privacy": body["status"]["privacyStatus"],
        },
        ledger=ledger,
    )
    return f"https://youtube.com/watch?v={video_id}"


def get_service():
    """Build an authenticated YouTube service. Runs the OAuth installed-app flow
    on first use (opens a browser) and caches a refresh token at config.YT_TOKEN."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token_path = Path(config.YT_TOKEN)
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), config.YT_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(config.YT_CLIENT_SECRET, config.YT_SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def main(argv=None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="publish.youtube",
        description="Upload one rendered clip to YouTube (private by default).",
    )
    parser.add_argument("clip_dir", help="Path to a clip directory (holds clip_NN.mp4 + meta.json)")
    parser.add_argument("--public", action="store_true", help="Publish public immediately (default: private)")
    args = parser.parse_args(argv)
    try:
        url = upload(args.clip_dir, public=args.public)
    except rights.RightsError as e:
        raise SystemExit(str(e))
    print(url)


if __name__ == "__main__":
    main()
