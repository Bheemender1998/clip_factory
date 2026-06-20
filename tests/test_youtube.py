import json

import pytest

from clipper import config
from publish import youtube
from publish import rights


def test_youtube_body_private_by_default():
    body = youtube.youtube_body({"title": "T", "caption": "C", "hashtags": ["#a"]}, public=False)
    assert body["status"]["privacyStatus"] == "private"


def test_youtube_body_public_flag():
    body = youtube.youtube_body({"title": "T", "caption": "C", "hashtags": []}, public=True)
    assert body["status"]["privacyStatus"] == "public"


def test_youtube_body_maps_tags_category_and_shorts():
    meta = {"title": "T", "caption": "C", "hashtags": ["#cat", "#dog"]}
    body = youtube.youtube_body(meta, public=False)
    assert body["snippet"]["title"] == "T"
    assert body["snippet"]["tags"] == ["cat", "dog"]
    assert body["snippet"]["categoryId"] == config.YT_CATEGORY
    assert "#Shorts" in body["snippet"]["description"]
    assert body["snippet"]["description"].startswith("C")


def test_log_upload_appends_jsonl(tmp_path):
    ledger = tmp_path / "uploads.jsonl"
    youtube.log_upload({"video_id": "v1", "source": "s", "privacy": "private", "clip_dir": "d"}, ledger=ledger)
    youtube.log_upload({"video_id": "v2", "source": "s", "privacy": "public", "clip_dir": "d"}, ledger=ledger)
    lines = ledger.read_text().strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["video_id"] == "v1"
    assert "ts" in first
