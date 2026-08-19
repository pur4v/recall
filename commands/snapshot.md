---
description: Re-render every captured session now (what the interval scheduler runs)
argument-hint: ""
---

Force a snapshot: re-render **all** captured sessions to Markdown right now.

1. Run `python3 skills/recall/scripts/recall.py snapshot`. It regenerates every
   `~/.recall/sessions/<id>.md` from the raw streams (redacting secrets) and rebuilds `index.md`.
2. Report how many sessions were rendered and where they live.

This is exactly what the interval scheduler (`reference/scheduler.md`) runs on a timer so that a
force-closed terminal is still captured. Run it manually after adding a new redaction pattern to
`assets/redaction-patterns.txt` (to re-redact already-captured sessions), or any time you want the
rendered files brought fully up to date.
