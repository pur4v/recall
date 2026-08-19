#!/bin/sh
# recall.sh — fast dispatcher for the recall terminal-history skill.
#
# The per-command `log` path is pure POSIX shell (no interpreter spawn) so it adds no
# noticeable latency to your prompt. Everything else forwards to recall.py.
#
# Env it honours: RECALL_HOME (default ~/.recall), RECALL_SESSION_ID, RECALL_CMD.

set -u

DIR=$(unset CDPATH; cd -- "$(dirname -- "$0")" && pwd)
: "${RECALL_HOME:=$HOME/.recall}"
export RECALL_HOME

cmd=${1:-}
[ "$#" -gt 0 ] && shift

case "$cmd" in
  log)
    # log <exit> <dur_ms> <cwd> -- <command...>
    ex=${1:-0}
    dur=${2:-0}
    cwd=${3:-$PWD}
    [ "$#" -ge 3 ] && shift 3
    [ "${1:-}" = "--" ] && shift
    cmd_str=$*
    [ -n "$cmd_str" ] || exit 0
    : "${RECALL_CMD:=$RECALL_HOME/cmd/${RECALL_SESSION_ID:-unknown}.jsonl}"
    mkdir -p "$(dirname "$RECALL_CMD")" 2>/dev/null || true
    ts=$(date +%s)
    # JSON-encode safely in awk (escape backslash, quote, tab; join multi-line with \n).
    printf '%s\n' "$cmd_str" | awk -v ex="$ex" -v dur="$dur" -v cwd="$cwd" -v ts="$ts" '
      function esc(s){ gsub(/\\/,"\\\\",s); gsub(/"/,"\\\"",s); gsub(/\t/,"\\t",s); gsub(/\r/,"",s); return s }
      { c = (seen ? c "\\n" : "") esc($0); seen=1 }
      END { printf "{\"ts\":%d,\"exit\":%d,\"dur_ms\":%d,\"cwd\":\"%s\",\"cmd\":\"%s\"}\n", ts+0, ex+0, dur+0, esc(cwd), c }
    ' >> "$RECALL_CMD" 2>/dev/null || true
    ;;
  ""|help|-h|--help)
    echo "usage: recall <setup|begin|log|finalize|snapshot|ingest|render|list|show|search|resume|redact> ..."
    ;;
  *)
    exec python3 "$DIR/recall.py" "$cmd" "$@"
    ;;
esac
