#!/bin/sh
# install-scheduler.sh — install (or remove) the interval snapshotter that periodically
# re-renders open sessions to Markdown, so nothing is lost if a terminal is force-closed.
#   macOS -> a launchd LaunchAgent (StartInterval)
#   Linux -> a crontab line
#
# Usage: sh install-scheduler.sh [--interval SECONDS] [--uninstall]

set -u

DIR=$(unset CDPATH; cd -- "$(dirname -- "$0")" && pwd)
CLI="$DIR/recall.sh"
INTERVAL=300
ACTION=install

while [ "$#" -gt 0 ]; do
  case "$1" in
    --interval) INTERVAL=${2:-300}; shift 2 ;;
    --uninstall) ACTION=uninstall; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

case "$(uname -s)" in
  Darwin)
    PLIST="$HOME/Library/LaunchAgents/com.pur4v.recall.plist"
    if [ "$ACTION" = uninstall ]; then
      launchctl unload "$PLIST" 2>/dev/null || true
      rm -f "$PLIST"
      echo "recall: removed $PLIST"
      exit 0
    fi
    mkdir -p "$HOME/Library/LaunchAgents"
    sed -e "s#@CLI@#$CLI#g" -e "s#@INTERVAL@#$INTERVAL#g" \
      "$DIR/../assets/com.pur4v.recall.plist" > "$PLIST"
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST" && echo "recall: loaded $PLIST (every ${INTERVAL}s)"
    ;;
  *)
    MINUTES=$(( (INTERVAL + 59) / 60 ))
    [ "$MINUTES" -lt 1 ] && MINUTES=1
    LINE="*/$MINUTES * * * * $CLI snapshot >/dev/null 2>&1"
    TMP=$(mktemp)
    crontab -l 2>/dev/null | grep -v 'recall.sh snapshot' > "$TMP" || true
    if [ "$ACTION" != uninstall ]; then
      echo "$LINE" >> "$TMP"
      crontab "$TMP" && echo "recall: cron installed (every ${MINUTES}m)"
    else
      crontab "$TMP" && echo "recall: cron removed"
    fi
    rm -f "$TMP"
    ;;
esac
