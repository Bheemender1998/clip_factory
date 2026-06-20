# YouTube Manual Uploader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `publish/youtube.py` command that uploads one rendered clip to a single user-owned YouTube channel, gated by the `SOURCES.md` rights allowlist, private by default.

**Architecture:** New `publish/` package. `publish/rights.py` is a pure rights gate (parses `SOURCES.md`, no network). `publish/youtube.py` holds a pure `meta.json`→YouTube body mapper, a jsonl upload log, an injectable `upload()` orchestrator, an OAuth `get_service()` (installed-app flow, cached refresh token), and an argparse CLI. Google API libraries are imported lazily inside the functions that need them — exactly like `clipper` imports `anthropic` lazily — so the pure functions and `upload()` are unit-testable with fakes and no Google libraries installed.

**Tech Stack:** Python 3, `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`, pytest.

## Global Constraints

- **`python3`, not `python`** — no `python` binary on this machine.
- **All imports absolute** (`from clipper import config`, `from publish import rights`) — run via `python3 -m publish.youtube`.
- **Single venv** (`.venv`).
- **Secrets are gitignored** — `secrets/` is already in `.gitignore`; never commit `secrets/client_secret.json` or `secrets/youtube_token.json`.
- **Never push `main` directly / never work on `main`.** This work lives on branch `feat/youtube-uploader` (already created and checked out).
- **Run `python3 -m pytest tests/ -q` after each task.** (The `clipper-test` hook auto-runs only on `clipper/**.py` edits; `publish/**.py` edits do NOT trigger it, so run pytest manually each task.)
- **No real API calls / no uploads in tests, hooks, or CI** — same rule as render. `get_service()` and `_insert()` are never exercised against live Google in tests; tests inject fakes.
- **Rights gate fails closed** — any source not matching an `## Authorized` token in `SOURCES.md` (including every `ytsearch:` source) is refused. No `--force` override in v1.
- **Smallest sufficient change** — YouTube only, single clip, manual. No batch/scheduler/other platforms.

---

### Task 1: Rights gate (`publish/rights.py`)

**Files:**
- Create: `publish/__init__.py`
- Create: `publish/rights.py`
- Modify: `clipper/config.py` (add `SOURCES_MD`)
- Test: `tests/test_rights.py`

**Interfaces:**
- Consumes: `clipper.config.ROOT` (existing `Path`).
- Produces:
  - `config.SOURCES_MD: Path`
  - `rights.is_authorized(source: str, *, sources_md: Path = None) -> bool`
  - `rights.check_rights(source: str, *, sources_md: Path = None) -> None` (raises `rights.RightsError`)
  - `rights.RightsError(Exception)`

- [ ] **Step 1: Add config constant**

In `clipper/config.py`, after the `OUTPUT_DIR`/`WORK_DIR` lines, add:

```python
# --- Stage 2: YouTube publishing ---
SOURCES_MD = ROOT / "SOURCES.md"
```

- [ ] **Step 2: Create the package init**

Create `publish/__init__.py` (empty file):

```python
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_rights.py`:

```python
import pytest

from publish import rights


def _md(tmp_path, body):
    p = tmp_path / "SOURCES.md"
    p.write_text(body)
    return p


def test_authorized_when_source_matches_token(tmp_path):
    md = _md(tmp_path, "## Authorized\n- **Chan** — https://youtube.com/@chan — owner — 2026-06-19\n")
    assert rights.is_authorized("https://youtube.com/@chan/watch?v=abc", sources_md=md)


def test_unlisted_source_blocked(tmp_path):
    md = _md(tmp_path, "## Authorized\n- **Chan** — https://youtube.com/@chan — owner — 2026-06-19\n")
    assert not rights.is_authorized("https://youtube.com/@someoneelse", sources_md=md)


def test_ytsearch_source_blocked(tmp_path):
    md = _md(tmp_path, "## Authorized\n- **Chan** — https://youtube.com/@chan — owner — 2026-06-19\n")
    assert not rights.is_authorized("ytsearch:funny cats", sources_md=md)


def test_format_section_tokens_ignored(tmp_path):
    md = _md(tmp_path, "## Format\n- **<name>** — <channel/URL> — <basis> — <date>\n## Authorized\n_(none yet)_\n")
    assert not rights.is_authorized("https://youtube.com/@chan", sources_md=md)


def test_empty_source_blocked(tmp_path):
    md = _md(tmp_path, "## Authorized\n- **Chan** — https://youtube.com/@chan — owner — 2026-06-19\n")
    assert not rights.is_authorized("", sources_md=md)


def test_check_rights_raises_on_unauthorized(tmp_path):
    md = _md(tmp_path, "## Authorized\n_(none yet)_\n")
    with pytest.raises(rights.RightsError):
        rights.check_rights("ytsearch:x", sources_md=md)


def test_check_rights_passes_on_authorized(tmp_path):
    md = _md(tmp_path, "## Authorized\n- **Chan** — https://youtube.com/@chan — owner — 2026-06-19\n")
    rights.check_rights("https://youtube.com/@chan/watch?v=abc", sources_md=md)  # no raise
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_rights.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'publish.rights'`

- [ ] **Step 5: Implement `publish/rights.py`**

```python
from pathlib import Path

from clipper import config


def _authorized_tokens(sources_md: Path) -> list[str]:
    """Pull the channel/URL token (the 2nd em-dash-delimited field) from each
    bullet under the '## Authorized' heading of SOURCES.md, lowercased."""
    text = sources_md.read_text() if sources_md.exists() else ""
    tokens: list[str] = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_section = line.strip().lower() == "## authorized"
            continue
        if in_section and line.lstrip().startswith("-"):
            parts = line.split("—")  # em dash U+2014, per SOURCES.md format
            if len(parts) >= 2:
                tok = parts[1].strip().lower()
                if tok:
                    tokens.append(tok)
    return tokens


def is_authorized(source: str, *, sources_md: Path = None) -> bool:
    """True iff `source` contains an authorized token. Fails closed: an empty
    source, an unlisted source, or any ytsearch: term returns False."""
    sources_md = sources_md or config.SOURCES_MD
    src = (source or "").strip().lower()
    if not src:
        return False
    return any(tok in src for tok in _authorized_tokens(sources_md))


class RightsError(Exception):
    """Raised when a clip's source is not on the SOURCES.md allowlist."""


def check_rights(source: str, *, sources_md: Path = None) -> None:
    if not is_authorized(source, sources_md=sources_md):
        raise RightsError(
            f"Source not authorized for upload: {source!r}\n"
            f"Add it to the '## Authorized' section of SOURCES.md "
            f"(format: - **<name>** — {source} — <rights basis> — <date>) and re-run."
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_rights.py -q`
Expected: PASS (7 passed)

- [ ] **Step 7: Commit**

```bash
git add publish/__init__.py publish/rights.py clipper/config.py tests/test_rights.py
git commit -m "feat(publish): SOURCES.md rights gate for uploads

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Metadata mapping (`youtube_body`)

**Files:**
- Create: `publish/youtube.py`
- Modify: `clipper/config.py` (add `YT_CATEGORY`)
- Test: `tests/test_youtube.py`

**Interfaces:**
- Consumes: `clipper.config.YT_CATEGORY`.
- Produces: `youtube.youtube_body(meta: dict, *, public: bool) -> dict` returning
  `{"snippet": {"title","description","tags","categoryId"}, "status": {"privacyStatus"}}`.

- [ ] **Step 1: Add config constant**

In `clipper/config.py`, under the `# --- Stage 2: YouTube publishing ---` block, add:

```python
YT_CATEGORY = os.environ.get("CLIP_YT_CATEGORY", "22")  # 22 = People & Blogs
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_youtube.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_youtube.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'publish.youtube'`

- [ ] **Step 4: Implement `publish/youtube.py` (mapping only)**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_youtube.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add publish/youtube.py clipper/config.py tests/test_youtube.py
git commit -m "feat(publish): map meta.json to YouTube request body

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Upload log (`log_upload`)

**Files:**
- Modify: `publish/youtube.py` (add `log_upload`)
- Modify: `clipper/config.py` (add `UPLOAD_LOG`)
- Test: `tests/test_youtube.py` (append)

**Interfaces:**
- Consumes: `clipper.config.UPLOAD_LOG`.
- Produces: `youtube.log_upload(record: dict, *, ledger: Path = None) -> dict` — appends one
  json line `{"ts", **record}` to the ledger, creating the parent dir.

- [ ] **Step 1: Add config constant**

In `clipper/config.py`, under the Stage-2 block, add:

```python
UPLOAD_LOG = ROOT / "logs" / "uploads.jsonl"
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_youtube.py`:

```python
def test_log_upload_appends_jsonl(tmp_path):
    ledger = tmp_path / "uploads.jsonl"
    youtube.log_upload({"video_id": "v1", "source": "s", "privacy": "private", "clip_dir": "d"}, ledger=ledger)
    youtube.log_upload({"video_id": "v2", "source": "s", "privacy": "public", "clip_dir": "d"}, ledger=ledger)
    lines = ledger.read_text().strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["video_id"] == "v1"
    assert "ts" in first
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_youtube.py::test_log_upload_appends_jsonl -q`
Expected: FAIL with `AttributeError: module 'publish.youtube' has no attribute 'log_upload'`

- [ ] **Step 4: Implement `log_upload` in `publish/youtube.py`**

Add after `youtube_body`:

```python
def log_upload(record: dict, *, ledger: Path = None) -> dict:
    """Append one upload record to logs/uploads.jsonl (local record + daily-quota
    tally + Stage-3 seed)."""
    ledger = ledger or config.UPLOAD_LOG
    rec = {"ts": time.time(), **record}
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_youtube.py -q`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add publish/youtube.py clipper/config.py tests/test_youtube.py
git commit -m "feat(publish): jsonl upload log

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Upload orchestration, OAuth, and CLI

**Files:**
- Modify: `publish/youtube.py` (add `_insert`, `upload`, `get_service`, `main`)
- Modify: `clipper/config.py` (add `YT_CLIENT_SECRET`, `YT_TOKEN`, `YT_SCOPES`)
- Modify: `requirements` (add Google libraries)
- Test: `tests/test_youtube.py` (append)

**Interfaces:**
- Consumes: `youtube.youtube_body`, `youtube.log_upload`, `rights.check_rights`,
  `config.YT_CLIENT_SECRET`, `config.YT_TOKEN`, `config.YT_SCOPES`.
- Produces:
  - `youtube._insert(service, body: dict, video_path: Path) -> dict` (returns `{"id": ...}`)
  - `youtube.upload(clip_dir, *, public=False, service=None, sources_md=None, ledger=None) -> str` (watch URL)
  - `youtube.get_service()` (authenticated client; not unit-tested)
  - `youtube.main(argv=None) -> None`

- [ ] **Step 1: Add config constants**

In `clipper/config.py`, under the Stage-2 block, add:

```python
YT_CLIENT_SECRET = os.environ.get("CLIP_YT_CLIENT_SECRET", str(ROOT / "secrets" / "client_secret.json"))
YT_TOKEN = os.environ.get("CLIP_YT_TOKEN", str(ROOT / "secrets" / "youtube_token.json"))
YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
```

- [ ] **Step 2: Add dependencies**

Append to `requirements`:

```
google-api-python-client
google-auth-oauthlib
google-auth-httplib2
```

Then install into the venv:

Run: `python3 -m pip install google-api-python-client google-auth-oauthlib google-auth-httplib2`
Expected: installs succeed (or "already satisfied").

- [ ] **Step 3: Write the failing tests**

Append to `tests/test_youtube.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_youtube.py -q`
Expected: FAIL — `AttributeError: module 'publish.youtube' has no attribute 'upload'` (and `_insert`).

- [ ] **Step 5: Implement upload, _insert, get_service, main in `publish/youtube.py`**

Add after `log_upload`:

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_youtube.py -q`
Expected: PASS (7 passed)

- [ ] **Step 7: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: PASS (all prior tests + new ones).

- [ ] **Step 8: Commit**

```bash
git add publish/youtube.py clipper/config.py requirements tests/test_youtube.py
git commit -m "feat(publish): YouTube upload orchestration, OAuth, CLI

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Docs

**Files:**
- Modify: `CLAUDE.md` (Layout table `publish/` row; Entrypoints)
- Modify: `README.md` (usage)

**Interfaces:** none (docs only).

- [ ] **Step 1: Update CLAUDE.md layout row**

In `CLAUDE.md`, change the `publish/` layout row from the planned line to:

```markdown
| `publish/youtube.py` + `rights.py` | Stage 2: manual single-clip YouTube upload, SOURCES.md-gated | LIVE (YouTube only) |
```

- [ ] **Step 2: Add the entrypoint to CLAUDE.md**

In the Entrypoints block, add:

```bash
python3 -m publish.youtube output/<vid>/clip_03           # upload one clip (PRIVATE; --public to go live)
```

- [ ] **Step 3: Add usage to README.md**

Add a short "Publishing (Stage 2)" subsection to `README.md`:

```markdown
## Publishing (Stage 2 — YouTube, manual)

Upload one rendered clip to your YouTube channel (private by default; `--public` to go live):

```bash
python3 -m publish.youtube output/<vid>/clip_03
```

First run opens a browser once for Google OAuth consent and caches a refresh token at
`secrets/youtube_token.json`. Requires `secrets/client_secret.json` (a Desktop-app OAuth
client from a Google Cloud project with the YouTube Data API v3 enabled). The clip's
`source` must be listed in `SOURCES.md` or the upload is refused. API uploads are capped
at ~6/day by the default 10,000-unit YouTube quota.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: Stage-2 YouTube uploader usage

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## After all tasks

- [ ] **Adversarial review** (per `ship-change`: Codex and/or a code-reviewer agent; gate: 0 Critical + 0 Important).
- [ ] **Live smoke test (local, user-run):** add one real authorized source to `SOURCES.md`, then `python3 -m publish.youtube output/<vid>/clip_NN` — confirm browser consent, a private video appears in YouTube Studio, and a line lands in `logs/uploads.jsonl`. (Real upload — not in a hook/CI; counts ~1,600 quota units.)
- [ ] **Open PR** `feat/youtube-uploader` → `main` via `gh` (push the branch from your own terminal first; the shell push-guard blocks the agent).
