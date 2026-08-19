---
name: recall
description: >-
  Capture and recall terminal session history so a closed or crashed terminal is never lost.
  Use when you want a per-terminal record of what you ran — every command (with cwd, exit code,
  and duration) and, when possible, the full output — saved as a clean, secret-redacted Markdown
  file per session under `~/.recall`, plus an interval snapshotter that re-renders open sessions
  on a timer so nothing is lost even if a window is force-closed. recall installs a lightweight
  shell integration (zsh + bash, macOS + Linux) that records live per command and transparently
  records output via `script`, degrading to a complete commands-only log when output capture
  can't start ("works all the time"). It then renders `sessions/<id>.md` + an `index.md`, and
  answers list / show / search / resume queries — including a `resume` that reprints the last
  window's directory and recent commands so you can pick up exactly where you left off. Triggers:
  "save my terminal history", "what did I run in that closed terminal", "recall my last session",
  "record terminal output to a file", "resume where I left off in the terminal", "snapshot my
  shell sessions on a timer". Secrets are redacted before anything is written; the store is
  private (chmod 700) and never committed.
---

# recall

`recall` gives every terminal window a durable memory. It records what you run — **live, per
command** — and, when it can, the **full output**, then renders each session to a clean,
**secret-redacted** Markdown file. Close the terminal, reboot the laptop, or lose the window to a
crash: the history is already on disk, and an interval snapshotter re-renders open sessions on a
timer so even an ungraceful close leaves a complete record.

The guiding idea: **capture cheaply, render richly, never lose data.** The hot path (logging a
command) is pure shell so it adds no noticeable prompt latency; everything expensive (rendering,
redaction, indexing) happens out of band.

```
your shell ──hooks──►  ~/.recall/cmd/<id>.jsonl   (every command: ts, exit, dur, cwd)
           ──script──► ~/.recall/raw/<id>.log      (full output, when capture is on)
                              │
                        recall render / snapshot / finalize
                              ▼
                    ~/.recall/sessions/<id>.md  +  ~/.recall/index.md   (redacted, readable)
```

## What it captures

Two low-level streams per session, under `$RECALL_HOME` (default `~/.recall`):

- **`cmd/<id>.jsonl`** — one JSON record per command: timestamp, exit code, duration, cwd, and
  the command line. Written by the shell hook in pure POSIX shell (no interpreter spawn).
- **`raw/<id>.log`** — the raw `script` typescript (full terminal output), when output capture is
  on. recall transparently re-execs your shell under `script` exactly once per window.
- **`meta/<id>.json`** — session metadata: start/end, host, shell, tty, and a window hint
  (iTerm/terminal session id, `$WINDOWID`, or `$TMUX_PANE`).

From those, `recall.py` renders `sessions/<id>.md` (a table of commands + a cleaned transcript)
and `index.md` (all sessions, newest first).

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
- **Never committed.** Captured history lives in `~/.recall`, never in a repo. `scan_secrets.sh`
  (run in CI) fails if any `.recall/`, `raw/`, `*.log`, `*.jsonl`, or `sessions/*.md` artifact is
  tracked, or if a credential-shaped value appears in a tracked file.

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

The engine behind them is `scripts/recall.py` (render/query, stdlib only) with `scripts/recall.sh`
as a fast dispatcher; the shell integrations are `scripts/recall.{zsh,bash}`.

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
- `sessions/<id>.md` — the rendered, redacted, human-readable transcript per session.
- `index.md` — every session, newest first, with window / cmd count / last dir / first command.

## Output principles

- Lead with the answer (which session, what you last ran, where you were), then the detail.
- Prefer the rendered table + transcript over dumping raw logs.
- Redaction is a floor, not a ceiling — if output *might* contain a secret a pattern misses, treat
  it as sensitive. recall never commits captured data and keeps the store private by default.
