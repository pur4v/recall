<!--
  Reference for the per-session file recall renders to $RECALL_HOME/sessions/<id>.md.
  This is documentation of the OUTPUT SHAPE — recall.py (render_session) generates the real file
  from cmd/<id>.jsonl + raw/<id>.log + meta/<id>.json. Placeholders in {{ }}.
  Every command and every transcript line is secret-redacted before it is written here.
-->
# Terminal session `{{session_id}}`

| | |
|---|---|
| Started | {{started_iso}} |
| Status | {{**active** | ended <iso>}} |
| Host | {{hostname}} |
| Shell | {{/bin/zsh}} |
| TTY | {{/dev/ttys00N}} |
| Window | `{{window_hint}}` |
| Commands | {{count}} |
| Last dir | `{{~/abbreviated/last/cwd}}` |
| Output capture | {{on (transcript below) | off (commands only)}} |

## Commands

| Time | Dir | Command | Exit | Duration |
|---|---|---|---|---|
| {{HH:MM:SS}} | `{{~/dir}}` | `{{command, redacted}}` | {{0}} | {{123ms}} |
| {{HH:MM:SS}} | `{{~/dir}}` | `{{command, redacted}}` | {{1 ⚠️}} | {{2.4s}} |

<!-- Non-zero exit codes are flagged with ⚠️. If no commands: "_No commands recorded yet._" -->

## Transcript (commands + output)

<!-- Present only when output capture was on (raw/<id>.log exists). The raw `script` typescript
     is cleaned (CRLF normalized, carriage-return redraws collapsed, ANSI/control stripped,
     Script started/done dropped) and redacted. -->
```text
{{cleaned, redacted transcript}}
```

---
_Rendered by recall at {{render_iso}}. Secrets redacted as `«redacted»`._
