# recall — zsh integration. Source this from ~/.zshrc:
#     source /path/to/recall/skills/recall/scripts/recall.zsh
#
# It captures every command (with cwd, exit code, duration) live, and — when possible —
# records the full session output transparently via `script`, so a closed/reopened terminal
# can be reconstructed. Everything degrades gracefully: if output capture can't start, you
# still get a complete command log ("works all the time").

# Only for real interactive shells; never in CI, dumb terminals, or when explicitly disabled.
[[ -o interactive ]] || return 0
[[ -n ${RECALL_DISABLE:-} ]] && return 0
[[ -n ${CI:-} ]] && return 0
[[ ${TERM:-} == dumb ]] && return 0

: ${RECALL_HOME:=$HOME/.recall}
export RECALL_HOME
export RECALL_DIR=${0:A:h}
export RECALL_CLI="$RECALL_DIR/recall.sh"

# One stable id + window hint per terminal (inherited across the script re-exec below).
if [[ -z ${RECALL_SESSION_ID:-} ]]; then
  export RECALL_SESSION_ID="$(date +%s)-$$-${RANDOM}"
  export RECALL_WINDOW="${ITERM_SESSION_ID:-${TERM_SESSION_ID:-${WINDOWID:-${TMUX_PANE:-tty}}}}"
  export RECALL_TTY="$(tty 2>/dev/null)"
fi
export RECALL_RAW="$RECALL_HOME/raw/$RECALL_SESSION_ID.log"
export RECALL_CMD="$RECALL_HOME/cmd/$RECALL_SESSION_ID.jsonl"

# Transparent output recording: re-exec this shell under `script` exactly once. The inner
# shell re-sources this file with RECALL_RECORDING=1 set, so it installs hooks instead of
# recursing. Guarded heavily so it never wedges a session.
if [[ -z ${RECALL_RECORDING:-} && ${RECALL_CAPTURE_OUTPUT:-1} == 1 && -z ${RECALL_NO_SCRIPT:-} && -t 1 ]]; then
  if command -v script >/dev/null 2>&1; then
    mkdir -p "$RECALL_HOME/raw"
    export RECALL_RECORDING=1
    case "$(uname -s)" in
      Darwin|*BSD) exec script -q "$RECALL_RAW" "$SHELL" ;;
      *)           exec script -q -f -c "$SHELL" "$RECALL_RAW" ;;
    esac
    # If exec fell through (script failed), continue unrecorded.
    unset RECALL_RECORDING
  fi
fi

# Register the session (idempotent) — records start/host/shell/tty/window.
"$RECALL_CLI" begin >/dev/null 2>&1

# Per-command capture via zsh hooks.
zmodload zsh/datetime 2>/dev/null
autoload -Uz add-zsh-hook

_recall_preexec() {
  _RECALL_CMD=$1
  _RECALL_T0=$EPOCHREALTIME
}

_recall_precmd() {
  local ex=$?
  [[ -z ${_RECALL_CMD:-} ]] && return
  local dur=0
  if [[ -n ${_RECALL_T0:-} ]]; then
    dur=$(( (EPOCHREALTIME - _RECALL_T0) * 1000 ))
  fi
  "$RECALL_CLI" log "$ex" "${dur%.*}" "$PWD" -- "$_RECALL_CMD" >/dev/null 2>&1
  _RECALL_CMD=""
}

_recall_zshexit() {
  "$RECALL_CLI" finalize "$RECALL_SESSION_ID" >/dev/null 2>&1
}

add-zsh-hook preexec _recall_preexec
add-zsh-hook precmd _recall_precmd
add-zsh-hook zshexit _recall_zshexit
