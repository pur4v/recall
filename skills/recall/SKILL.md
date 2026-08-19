---
name: recall
description: >-
  Capture and recall a terminal window's entire working context so a closed or crashed terminal is
  never lost. Use when you want a per-terminal record not just of what you ran — every command
  (with cwd, exit code, and duration) and, when possible, the full output — but of the whole
  context around it: the AI CLI conversation you had in that window (Claude Code, aider, and other
  agents via pluggable adapters), the files you changed and their diff, the git state (branch,
  commits made, dirty), and the directory + environment trail. It all renders to a clean,
  secret-redacted Markdown file per session under `~/.recall`, named by a meaningful title (from
  the conversation or the work) so the filename tells you what the session was about — plus an
  interval snapshotter that re-renders open sessions on a timer so nothing is lost even if a window
  is force-closed. recall installs a lightweight shell integration (zsh + bash, macOS + Linux) that
  records live per command and transparently records output via `script`, degrading to a complete
  commands-only log when output capture can't start ("works all the time"). It then renders titled
  session files + an `index.md`, ingests + correlates conversations by cwd and time, and answers
  list / show / search / resume / ingest queries — including a `resume` that reprints the last
  window's directory and recent commands so you can pick up exactly where you left off. Triggers:
  "save my terminal history", "what did I run in that closed terminal", "recall my last session",
  "store the whole context of my terminal", "keep my AI CLI conversation with the session",
  "record terminal output to a file", "resume where I left off in the terminal", "snapshot my
  shell sessions on a timer". Secrets are redacted before anything is written; the store is
  private (chmod 700) and never committed.
---

# recall

`recall` gives every terminal window a durable memory of its **entire working context**. It records
what you run — **live, per command** — and, when it can, the **full output**; it also ingests the
**AI CLI conversation** you had in that window, the **files you changed** (with diff), the **git
state**, and the **directory + environment trail**. All of it renders to a clean,
**secret-redacted** Markdown file, named by a meaningful **title** so the filename tells you what
the session was about. Close the terminal, reboot the laptop, or lose the window to a crash: the
context is already on disk, and an interval snapshotter re-renders open sessions on a timer so even
an ungraceful close leaves a complete record.

The guiding idea: **capture cheaply, render richly, never lose data.** The hot path (logging a
command) is pure shell so it adds no noticeable prompt latency; everything expensive (rendering,
redaction, conversation ingest, indexing) happens out of band.

```
your shell ──hooks──►  ~/.recall/cmd/<id>.jsonl   (every command: ts, exit, dur, cwd)
           ──script──► ~/.recall/raw/<id>.log      (full output, when capture is on)
AI CLI agents ─adapters─► ~/.recall/conv/*.json + conversations/*.md   (transcripts, ingested)
                              │
              recall render / ingest / snapshot / finalize  (correlate by cwd + time)
                              ▼
   ~/.recall/sessions/<title>--<id>.md  +  ~/.recall/index.md   (redacted, readable, titled)
       └─ commands · output · conversation · files changed & git · context trail
```

## What it captures

Two low-level streams per session, under `$RECALL_HOME` (default `~/.recall`):

- **`cmd/<id>.jsonl`** — one JSON record per command: timestamp, exit code, duration, cwd, and
  the command line. Written by the shell hook in pure POSIX shell (no interpreter spawn).
- **`raw/<id>.log`** — the raw `script` typescript (full terminal output), when output capture is
  on. recall transparently re-execs your shell under `script` exactly once per window.
- **`meta/<id>.json`** — session metadata: start/end, host, shell, tty, and a window hint
  (iTerm/terminal session id, `$WINDOWID`, or `$TMUX_PANE`).

From those, `recall.py` renders a titled `sessions/<title>--<id>.md` (command table + cleaned
transcript + the context sections below) and `index.md` (all sessions, newest first).

## The entire context, not just the shell

A terminal session is only half the story of what you were doing. recall folds in the rest, so a
recalled window carries the **whole** context (see `reference/context.md`):

- **Conversation.** The AI CLI agent transcript you had in that window — Claude Code, aider, and
  others via **pluggable adapters** (`scripts/adapters.py`, enabled with `RECALL_AGENTS`). Each
  agent's native store is normalized to one shape and rendered to a redacted transcript under
  `conversations/`, then **correlated** to the terminal session by working directory (or git root)
  and overlapping time window.
- **Files changed & git.** The repo, branch, commits made *during* the session, a per-file
  added/removed table, and a capped, redacted diff (raw patch in `diff/<id>.patch`).
- **Context trail.** Every directory visited (from the command log) and a small allow-listed
  snapshot of the environment at session start.

**Titled files.** Sessions and conversations are named by a meaningful title — the correlated
conversation's own title (Claude Code's `ai-title`, aider's first prompt) when there is one, else
the repo/last-dir plus the most distinctive commands — so the filename tells you the context. The
terminal id and title are stored in `meta/<id>.json` and shown in the session header; a stale file
is removed if the title changes on re-render.

## Works all the time (graceful degradation)

Output capture depends on `script`, a TTY, and a re-exec that must never wedge a shell. So it is
heavily guarded (`RECALL_CAPTURE_OUTPUT`, `RECALL_NO_SCRIPT`, `-t 1`, interactive-only) and, if it
can't start, recall **falls back to a complete commands-only log**. You always get *something*:
the command history is captured by shell hooks that don't depend on `script` at all. See
`reference/capture.md`.

## Two triggers: live + interval

1. **Live, per command.** zsh `preexec`/`precmd` hooks (and the bash `DEBUG` trap +
   `PROMPT_COMMAND`) append each command to the JSONL stream the instant it finishes, and
   `finalize` renders the session on shell exit.
2. **Interval snapshot.** A launchd LaunchAgent (macOS) or crontab line (Linux) runs
   `recall snapshot` every N seconds (default 300), re-rendering **all** sessions — so a window
   that is force-closed before its exit hook fires is still captured up to the last snapshot. See
   `reference/scheduler.md`.

## Privacy is not optional

- **Redaction before write.** Every command and every line of output is run through the patterns
  in `assets/redaction-patterns.txt` (AWS keys, `KEY=value` secrets, `export SECRET=…`, Bearer/
  Authorization headers, JWTs, `ghp_`/`xoxb-`/`sk-` tokens, PEM private-key headers) and replaced
  with `«redacted»` before anything reaches a `.md`.
- **Private store.** `~/.recall` is created `chmod 700`.
- **Never committed.** Captured history lives in `~/.recall`, never in a repo. Conversation turns,
  diffs, and commit subjects all pass through the same redaction before write. `scan_secrets.sh`
  (run in CI) fails if any `.recall/`, `raw/`, `*.log`, `*.jsonl`, `conversations/`, `diff/`, or
  `sessions/*.md` artifact is tracked, or if a credential-shaped value appears in a tracked file.

See `reference/privacy.md`.

## Commands

| Command | Does |
|---|---|
| `/recall:setup` | Print (or `--apply`) the shell-integration + scheduler install steps |
| `/recall:list` | List captured sessions, newest first (rebuilds `index.md`) |
| `/recall:show` | Render + print a session's Markdown (`last`, an id, or this window's prior session) |
| `/recall:search` | Grep all rendered sessions for a term (`session:line: match`) |
| `/recall:resume` | Reprint the last/this-window session's dir + recent commands to pick up where you left off |
| `/recall:snapshot` | Re-render every session now (what the interval scheduler runs) |
| `/recall:ingest` | Import AI CLI conversations (Claude Code, aider, …) so sessions carry their full context |

The engine behind them is `scripts/recall.py` (render/query/ingest, stdlib only) with
`scripts/recall.sh` as a fast dispatcher and `scripts/adapters.py` for the AI-agent conversation
adapters; the shell integrations are `scripts/recall.{zsh,bash}`.

## Standard workflow

1. **Install once.** `/recall:setup --apply` appends the `source …/recall.zsh` line to your
   rc file; `sh scripts/install-scheduler.sh --interval 300` installs the snapshotter. Open a new
   terminal — capture starts automatically.
2. **Work normally.** Every command is logged live; output is recorded when capture is on.
3. **Lost a terminal?** `/recall:list` to find it, `/recall:show <id>` to read it, or
   `/recall:resume` to reprint the last window's directory + recent commands (and the `cd` to get
   back).
4. **Force-closed before exit?** The interval snapshot already rendered it up to the last tick.

## Persistent workspace

recall keeps everything in **`$RECALL_HOME`** (default `~/.recall`), *not* in this skill repo —
the kit is generic and holds no captured data:

- `cmd/`, `raw/`, `meta/` — the low-level per-session streams.
- `conv/`, `conversations/`, `diff/` — cached conversation descriptors, rendered redacted AI
  transcripts, and per-session raw diffs.
- `sessions/<title>--<id>.md` — the rendered, redacted session: commands, output, conversation,
  files changed & git, and context trail. Titled so the filename tells you what it was about.
- `index.md` — every session, newest first, with title (linked) / status / cmd count / last dir /
  terminal id.

## Output principles

- Lead with the answer (which session, what you last ran, where you were), then the detail.
- Prefer the rendered table + transcript over dumping raw logs.
- Redaction is a floor, not a ceiling — if output *might* contain a secret a pattern misses, treat
  it as sensitive. recall never commits captured data and keeps the store private by default.
