---
description: Import AI CLI conversations (Claude Code, aider, …) so sessions carry their full context
argument-hint: ""
---

Ingest the **conversation history** from any AI CLI agent you ran, so a recalled terminal session
carries not just what you typed but the reasoning around it.

1. Run `python3 skills/recall/scripts/recall.py ingest`. This runs every enabled adapter
   (`RECALL_AGENTS`, default `claude-code,aider`), normalizes each conversation to a common shape,
   and renders a **secret-redacted** transcript per conversation to
   `~/.recall/conversations/<title>--<shortid>.md` — named by the conversation's own title so the
   filename tells you what it was about.
2. Report how many conversations were ingested and where they live.

Ingest is **idempotent** (keyed by agent + conversation id) and runs automatically on `finalize`
and `snapshot`, so you rarely call it by hand. Do so after starting a new agent you want picked up,
or after adding an adapter. When a session is next rendered, recall **correlates** conversations to
it by working directory (or git root) and overlapping time window, and inlines the matches under a
**Conversation** section alongside **Files changed & git** and the **Context trail**. See
`reference/context.md`.
