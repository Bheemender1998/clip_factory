#!/usr/bin/env bash
# PreToolUse(Bash): block a command that pushes to main directly.
set -euo pipefail
payload="$(cat)"
cmd="$(printf '%s' "$payload" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null || true)"
if printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+push'; then
  if printf '%s' "$cmd" | grep -Eq '(^|[[:space:]])main([[:space:]]|$)' \
     || [ "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" = "main" ]; then
    echo "On main: never push main directly. Branch (feat/...), open a PR, then merge." >&2
    exit 2
  fi
fi
exit 0
