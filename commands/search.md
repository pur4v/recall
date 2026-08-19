---
description: Search all captured sessions for a term
argument-hint: "<term>"
---

Search every captured terminal session for a term.

Term: `$1` (required).

1. Run `python3 skills/recall/scripts/recall.py search "$1"`. It re-renders each session (so
   matches are against the redacted, cleaned text) and prints `session:line: matching text` for
   every hit, case-insensitive.
2. Group the results by session and lead with the most relevant: which session, roughly when, and
   the matching command or output line.
3. If there are no matches, say so. Offer `/recall:show <id>` to open a session, or remind the
   user that only sessions captured since recall was installed are searchable.

Secrets are already redacted in the rendered files, so a search will never surface a credential
value even if the original command contained one.
