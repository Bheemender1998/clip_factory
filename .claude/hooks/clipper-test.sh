#!/usr/bin/env bash
# PostToolUse: after an Edit/Write/MultiEdit to clipper/**.py, run the test suite.
# Reads the hook payload (JSON) on stdin; only fires for clipper/*.py paths.
set -euo pipefail
payload="$(cat)"
file="$(printf '%s' "$payload" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null || true)"
case "$file" in
  *clipper/*.py)
    cd "$(git rev-parse --show-toplevel)"
    if ! python3 -m pytest tests/ -q >/tmp/clipper-pytest.log 2>&1; then
      echo "clipper tests FAILED after editing $file — see /tmp/clipper-pytest.log" >&2
      tail -20 /tmp/clipper-pytest.log >&2
      exit 2
    fi
    ;;
esac
exit 0
