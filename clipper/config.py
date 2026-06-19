import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
WORK_DIR = ROOT / "work"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("CLIP_MODEL", "claude-opus-4-8")
DEFAULT_CLIP_COUNT = int(os.environ.get("CLIP_COUNT", "6"))

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base.en")
WHISPER_COMPUTE = os.environ.get("WHISPER_COMPUTE", "int8")

# 9:16 render target
TARGET_W = 1080
TARGET_H = 1920
MIN_CLIP_SEC = 15.0
MAX_CLIP_SEC = 90.0

# $ per 1M tokens: (input, output)
PRICING = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
