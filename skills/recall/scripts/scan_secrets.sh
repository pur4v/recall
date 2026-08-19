#!/bin/sh
# scan_secrets.sh — guard the repo against committed secrets or captured session data.
# Scans tracked files (or a given path) for credential-shaped values and for any accidental
# recall workspace artifacts. Exits non-zero on a hit so CI fails loudly.

set -u

ROOT=${1:-.}
fail=0

# Files that should never be committed (captured history lives in ~/.recall, not the repo).
if git -C "$ROOT" ls-files 2>/dev/null | grep -Eq '(^|/)\.recall/|\.log$|\.jsonl$|/raw/|/sessions/.*\.md$'; then
  echo "scan_secrets: captured-session artifacts are tracked — they must not be committed" >&2
  git -C "$ROOT" ls-files | grep -E '(^|/)\.recall/|\.log$|\.jsonl$|/raw/' >&2
  fail=1
fi

# Credential-shaped values in tracked text. The redaction-patterns file legitimately contains
# pattern fragments, so exclude it from the value scan.
list_files() {
  if git -C "$ROOT" rev-parse >/dev/null 2>&1; then
    git -C "$ROOT" ls-files
  else
    find "$ROOT" -type f -not -path '*/.git/*'
  fi
}

while IFS= read -r f; do
  case "$f" in
    */redaction-patterns.txt|*/scan_secrets.sh|*/recall.py) continue ;;
  esac
  path="$ROOT/$f"
  [ -f "$path" ] || path="$f"
  if grep -Eq 'AKIA[0-9A-Z]{16}|-----BEGIN[^-]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}' "$path" 2>/dev/null; then
    echo "scan_secrets: possible secret in $f" >&2
    fail=1
  fi
done <<EOF
$(list_files)
EOF

if [ "$fail" -eq 0 ]; then
  echo "scan_secrets: clean."
fi
exit "$fail"
