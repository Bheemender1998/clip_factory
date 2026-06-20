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


def _clip(tmp_path, source, name="clip_01"):
    clip = tmp_path / name
    clip.mkdir()
    (clip / "meta.json").write_text(json.dumps(
        {"source": source, "title": "T", "caption": "C", "hashtags": ["#a"]}))
    (clip / f"{name}.mp4").write_bytes(b"fakebytes")
    return clip


def test_upload_blocks_unauthorized_source(tmp_path):
    clip = _clip(tmp_path, "ytsearch:funny")
    md = tmp_path / "SOURCES.md"
    md.write_text("## Authorized\n_(none yet)_\n")
    with pytest.raises(rights.RightsError):
        youtube.upload(clip, service=object(), sources_md=md)


def test_upload_authorized_logs_and_returns_url(tmp_path, monkeypatch):
    clip = _clip(tmp_path, "https://youtube.com/@chan/watch?v=abc")
    md = tmp_path / "SOURCES.md"
    md.write_text("## Authorized\n- **C** — https://youtube.com/@chan — owner — 2026-06-19\n")
    ledger = tmp_path / "uploads.jsonl"
    monkeypatch.setattr(youtube, "_insert", lambda service, body, path: {"id": "vid123"})
    url = youtube.upload(clip, public=False, service=object(), sources_md=md, ledger=ledger)
    assert url == "https://youtube.com/watch?v=vid123"
    rec = json.loads(ledger.read_text().strip())
    assert rec["video_id"] == "vid123"
    assert rec["privacy"] == "private"
    assert rec["source"] == "https://youtube.com/@chan/watch?v=abc"


def test_main_invokes_upload_and_prints_url(monkeypatch, capsys):
    seen = {}

    def fake_upload(clip_dir, *, public=False):
        seen["clip_dir"] = clip_dir
        seen["public"] = public
        return "https://youtube.com/watch?v=zzz"

    monkeypatch.setattr(youtube, "upload", fake_upload)
    youtube.main(["output/vid/clip_02", "--public"])
    assert seen["public"] is True
    assert "watch?v=zzz" in capsys.readouterr().out
