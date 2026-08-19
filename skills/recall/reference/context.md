# Full context: conversations, diffs, git & trail

recall started as a terminal-history tool, but a terminal session is only half the story of what
you were doing. The other half is the **AI conversation** you had in that window, the **files you
changed**, the **git state** around the work, and the **path** you took to get there. recall
captures all of it and folds it into each rendered session, so recalling a window gives you the
*whole* context — not just the commands.

## What each session bundles

A rendered `sessions/<title>--<shortid>.md` now contains, in addition to the command table and
output transcript:

1. **Conversation** — AI CLI agent transcripts correlated to this terminal (see below), each
   linking to its own full, redacted transcript under `conversations/`.
2. **Files changed & git** — the repo, branch, commits made *during* the session, a
   per-file added/removed table, and a (capped, redacted) diff. The raw patch is also written to
   `diff/<id>.patch`.
3. **Context trail** — every directory visited (derived from the command log) and a small
   allow-listed snapshot of the environment at session start.

## Titled files

Files are named by a **meaningful title**, not the opaque session id:
`add-greeting-feature-to-proj--195fa6.md`. The title is chosen in priority order:

1. the correlated AI conversation's own title (Claude Code's `ai-title`, aider's first prompt);
2. otherwise the repo/last-directory name plus the most distinctive commands run.

The `--<shortid>` suffix (a 6-char hash of the terminal id) keeps names unique and stable. The
terminal id and title are both stored in `meta/<id>.json` and shown in the session's header table,
so you never lose the mapping. If a title changes on re-render, the stale file is removed.

## Conversation adapters

Each AI CLI agent stores history differently, so recall uses one **adapter** per agent
(`scripts/adapters.py`) to normalize every conversation to a common shape:

```
{ agent, conv_id, cwd, source, title, started, ended,
  turns: [ {ts, role: "user"|"assistant", text}, ... ] }
```

Enabled adapters come from `RECALL_AGENTS` (default `claude-code,aider`). Adding an agent is one
function registered in `ADAPTERS` — everything downstream (rendering, redaction, correlation) is
agent-agnostic. Adapters degrade gracefully: if an agent's store is absent, it simply contributes
nothing, and one failing adapter never aborts the rest of the ingest.

- **claude-code** — reads `~/.claude/projects/<cwd-slug>/<uuid>.jsonl` (override the home with
  `CLAUDE_HOME`). Flattens typed content blocks (`text`, `thinking`, `tool_use`, `tool_result`) to
  readable text; set `RECALL_INCLUDE_THINKING=0` to drop thinking blocks. The title is the last
  `ai-title` record.
- **aider** — reads `.aider.chat.history.md` from directories recall already knows about (it can't
  scan the whole disk). `####` headings mark user turns; the title is the first prompt.

## Correlation

A conversation belongs to a terminal session when **both** hold:

- **Place** — the conversation's cwd is one of the session's visited directories, or lives under
  the session's git root.
- **Time** — the conversation's `[started, ended]` overlaps the session's `[started, ended]`.

Correlation happens at render time, so ingesting more conversations (or re-rendering) can enrich an
existing session without recapturing anything.

## When it runs

`ingest` runs automatically inside `finalize` (shell exit) and `snapshot` (the interval timer), so
conversations are picked up without any manual step. Run `/recall:ingest` by hand only to pull in a
brand-new agent transcript immediately, or after enabling a new adapter.

## Privacy

Everything here goes through the **same redaction** as commands and output before it is written —
conversation turns, diffs, commit subjects, and env values all pass through
`assets/redaction-patterns.txt` → `«redacted»`. Conversations and diffs live under `~/.recall`
(chmod 700) and are never committed; `scan_secrets.sh` covers `conversations/` and `diff/` too. See
`reference/privacy.md`.
