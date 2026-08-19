# recall — bash integration. Source this from ~/.bashrc:
#     source /path/to/recall/skills/recall/scripts/recall.bash
#
# Same idea as the zsh integration: live per-command capture + transparent `script` output
# recording, degrading to commands-only when recording can't start.

# Interactive shells only; never CI / dumb / disabled.
case $- in *i*) ;; *) return 0 ;; esac
[ -n "${RECALL_DISABLE:-}" ] && return 0
[ -n "${CI:-}" ] && return 0
[ "${TERM:-}" = dumb ] && return 0

: "${RECALL_HOME:=$HOME/.recall}"
export RECALL_HOME
RECALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export RECALL_DIR
export RECALL_CLI="$RECALL_DIR/recall.sh"

if [ -z "${RECALL_SESSION_ID:-}" ]; then
  export RECALL_SESSION_ID="$(date +%s)-$$-${RANDOM}"
  export RECALL_WINDOW="${ITERM_SESSION_ID:-${TERM_SESSION_ID:-${WINDOWID:-${TMUX_PANE:-tty}}}}"
  export RECALL_TTY="$(tty 2>/dev/null)"
fi
export RECALL_RAW="$RECALL_HOME/raw/$RECALL_SESSION_ID.log"
export RECALL_CMD="$RECALL_HOME/cmd/$RECALL_SESSION_ID.jsonl"

# Transparent output recording via `script`, once (see recall.zsh for the rationale).
if [ -z "${RECALL_RECORDING:-}" ] && [ "${RECALL_CAPTURE_OUTPUT:-1}" = 1 ] && [ -z "${RECALL_NO_SCRIPT:-}" ] && [ -t 1 ]; then
  if command -v script >/dev/null 2>&1; then
    mkdir -p "$RECALL_HOME/raw"
    export RECALL_RECORDING=1
    case "$(uname -s)" in
      Darwin|*BSD) exec script -q "$RECALL_RAW" "$SHELL" ;;
      *)           exec script -q -f -c "$SHELL" "$RECALL_RAW" ;;
    esac
    unset RECALL_RECORDING
  fi
fi

"$RECALL_CLI" begin >/dev/null 2>&1

# Capture the command about to run (DEBUG), then log it after it finishes (PROMPT_COMMAND).
_recall_debug() {
  [ -n "${COMP_LINE:-}" ] && return                 # skip completion
  [ "$BASH_COMMAND" = "${PROMPT_COMMAND:-}" ] && return
  case "$BASH_COMMAND" in _recall_*) return ;; esac
  _RECALL_CMD="$BASH_COMMAND"
  _RECALL_T0=$(date +%s%N 2>/dev/null || echo)
}
trap '_recall_debug' DEBUG

_recall_precmd() {
  local ex=$?
  [ -z "${_RECALL_CMD:-}" ] && return
  local dur=0 now
  now=$(date +%s%N 2>/dev/null || echo)
  if [ -n "${_RECALL_T0:-}" ] && [ -n "$now" ]; then
    dur=$(( (now - _RECALL_T0) / 1000000 ))
  fi
  "$RECALL_CLI" log "$ex" "$dur" "$PWD" -- "$_RECALL_CMD" >/dev/null 2>&1
  _RECALL_CMD=""
}
case "${PROMPT_COMMAND:-}" in
  *_recall_precmd*) ;;
  *) PROMPT_COMMAND="_recall_precmd${PROMPT_COMMAND:+; $PROMPT_COMMAND}" ;;
esac

trap '"$RECALL_CLI" finalize "$RECALL_SESSION_ID" >/dev/null 2>&1' EXIT
