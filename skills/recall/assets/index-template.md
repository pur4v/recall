<!--
  Reference for the session index recall renders to $RECALL_HOME/index.md.
  Documentation of the OUTPUT SHAPE — recall.py (rebuild_index) generates the real file from every
  session's meta + cmd streams, newest first. Placeholders in {{ }}.
-->
# Recall — session index

{{N}} session(s) captured. Newest first.

| Session | Started | Status | Window | Cmds | Last dir | First command |
|---|---|---|---|---|---|---|
| `{{session_id}}` | {{started_iso}} | {{active | ended}} | `{{window_hint}}` | {{count}} | `{{~/last/dir}}` | `{{first non-empty command}}` |
