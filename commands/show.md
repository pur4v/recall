---
description: Render and print a captured session's Markdown
argument-hint: "[session-id | last]"
---

Show a captured terminal session in full.

Target: `$1` (default: `last`).

1. Run `python3 skills/recall/scripts/recall.py show ${1:-last}`. This re-renders the session
   (redacting secrets), prints the path to `~/.recall/sessions/<id>.md`, and prints its contents:
   the metadata table, the command table (time / dir / command / exit ⚠️ / duration), and the
   cleaned output transcript when capture was on.
2. If `$1` is omitted or `last`, recall resolves the most recent session — or, if it can identify
   this terminal window, the prior session for *this* window (handy right after reopening a
   closed terminal). Pass an explicit id from `/recall:list` to show a specific one.
3. Summarize for the user: what they were doing, notable non-zero exits, and the last directory.
   Don't re-paste the whole transcript unless asked — lead with the answer.
