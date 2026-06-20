import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
WORK_DIR = ROOT / "work"

# --- Stage 2: YouTube publishing ---
SOURCES_MD = ROOT / "SOURCES.md"
YT_CATEGORY = os.environ.get("CLIP_YT_CATEGORY", "22")  # 22 = People & Blogs
UPLOAD_LOG = ROOT / "logs" / "uploads.jsonl"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("CLIP_MODEL", "claude-opus-4-8")
DEFAULT_CLIP_COUNT = int(os.environ.get("CLIP_COUNT", "6"))

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base.en")
WHISPER_COMPUTE = os.environ.get("WHISPER_COMPUTE", "int8")

# ffmpeg binary — override with CLIP_FFMPEG to point at a font-enabled build
# (the core Homebrew ffmpeg lacks libass/libfreetype, so it cannot burn captions).
FFMPEG = os.environ.get("CLIP_FFMPEG", "ffmpeg")

# 9:16 render target
TARGET_W = 1080
TARGET_H = 1920
# Clip length: aim for ~40s, hard-capped at 55s so every clip stays under
# YouTube's 60s Shorts threshold. Override via env.
MIN_CLIP_SEC = float(os.environ.get("CLIP_MIN_SEC", "20"))
TARGET_CLIP_SEC = float(os.environ.get("CLIP_TARGET_SEC", "40"))
MAX_CLIP_SEC = float(os.environ.get("CLIP_MAX_SEC", "55"))

# $ per 1M tokens: (input, output)
PRICING = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
