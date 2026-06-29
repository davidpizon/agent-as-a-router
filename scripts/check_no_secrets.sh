#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PATTERN='(sk-proj-[A-Za-z0-9_-]{24,}|sk-ant-[A-Za-z0-9_-]{24,}|sk-[A-Za-z0-9_]{32,}|ghp_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|ctx7sk-[0-9a-f-]{30,}|GOCSPX-[A-Za-z0-9_-]{20,}|[0-9]{12,}-[a-z0-9]{20,}\.apps\.googleusercontent\.com|xox[baprs]-[A-Za-z0-9-]{10,})'

if rg -n --hidden \
  --glob '!outputs/**' \
  --glob '!**/.git/**' \
  --glob '!**/__pycache__/**' \
  --glob '!scripts/check_no_secrets.sh' \
  "$PATTERN" "$ROOT"; then
  echo "Potential secret-like content found." >&2
  exit 1
fi

echo "No common API-key or bearer-token patterns found."
