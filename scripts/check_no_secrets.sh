#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PATTERN='(sk-[A-Za-z0-9_-]{16,}|OPENAI_API_KEY|ANTHROPIC_API_KEY|DASHSCOPE_API_KEY|IDEALAB_API_KEY|Authorization:[[:space:]]*Bearer[[:space:]]+[A-Za-z0-9._~+/-]{12,}|api[_-]?key[[:space:]]*[:=][[:space:]]*["'\''][^"'\'']{8,}["'\''])'

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
