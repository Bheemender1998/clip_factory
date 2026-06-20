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
