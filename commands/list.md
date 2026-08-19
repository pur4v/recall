---
description: List captured terminal sessions, newest first
argument-hint: ""
---

List every terminal session **recall** has captured.

1. Run `python3 skills/recall/scripts/recall.py list`. This rebuilds `~/.recall/index.md` and
   prints one line per session: id, status (ACTIVE / ended), command count, last directory, and
   the first command run.
2. Present the result newest-first. Point out any **ACTIVE** sessions (still-open or
   ungracefully-closed windows not yet finalized) vs ended ones.
3. If nothing is captured yet, say so and suggest `/recall:setup` to start capturing.

To read one, use `/recall:show <id>`; to pick up where a window left off, `/recall:resume`.
