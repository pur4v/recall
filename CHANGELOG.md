# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/); this project adheres to
[Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-08-19

### Added

- **The entire context, not just the shell.** A session now bundles far more than commands and
  output. Each rendered session carries, when available:
  - **Conversation** — the AI CLI agent transcript from that window, via **pluggable adapters**
    (`scripts/adapters.py`; enabled with `RECALL_AGENTS`, default `claude-code,aider`). Each
    agent's native store is normalized to one shape, rendered to a redacted transcript under
    `conversations/`, and **correlated** to the terminal session by working directory (or git
    root) and overlapping time window. Ships with **Claude Code** (`~/.claude/projects/**.jsonl`,
    flattening text/thinking/tool blocks; `RECALL_INCLUDE_THINKING=0` to drop thinking;
    `CLAUDE_HOME` override) and **aider** (`.aider.chat.history.md`) adapters.
  - **Files changed & git** — repo, branch, commits made during the session, a per-file
    added/removed table, and a capped, redacted diff (raw patch in `diff/<id>.patch`).
  - **Context trail** — every directory visited plus a small allow-listed snapshot of the
    environment at session start.
- **Titled session & conversation files.** Files are named by a meaningful title —
  `add-greeting-feature-to-proj--<shortid>.md` — taken from the correlated conversation's own title
  (Claude Code's `ai-title`, aider's first prompt) or derived from the repo/last-dir plus the most
  distinctive commands, so the filename tells you what the session was about. The terminal id and
  title are stored in `meta/<id>.json` and shown in the session header; a stale file is removed if
  the title changes on re-render.
- **`/recall:ingest`** command and `recall ingest` subcommand to import conversations on demand;
  ingest also runs automatically inside `finalize` and `snapshot`.
- `reference/context.md` documenting conversations, adapters, correlation, and titled files.

### Changed

- `index.md` now lists sessions by **title** (linked to the titled file) with the terminal id,
  instead of by opaque id.
- `show` / `resume` / `search` resolve a session by exact id, `last`, or a substring of the
  id / title / filename, and read the titled render path.
- Redaction now also covers conversation turns, diffs, commit subjects, and env values; the CI
  secret guard and `scan_secrets.sh` cover `conversations/` and `diff/`. CI gained a
  conversation-ingest self-check and now `py_compile`s `adapters.py`.

## [0.1.0] — 2026-08-19

### Added

- Initial release of the **recall** skill + Claude Code plugin: capture and recall terminal
  session history so a closed or crashed terminal is never lost. "Kit = tooling, data = yours" —
  captured history lives in `~/.recall`, never in the repo.
- **Layered capture that works all the time.** A pure-shell command log (zsh `preexec`/`precmd`;
  bash `DEBUG` trap + `PROMPT_COMMAND`) records every command (ts, exit, duration, cwd) with no
  interpreter spawn on the hot path, plus best-effort full-output recording via a transparent
  `script` re-exec that degrades to commands-only when it can't start.
- **Two triggers: live + interval.** Live per-command capture and on-shell-exit rendering, plus an
  interval snapshotter (launchd on macOS, cron on Linux) that re-renders all sessions on a timer
  so a force-closed window is still captured.
- **Cross-platform.** zsh + bash; macOS (BSD `script`, launchd) and Linux (util-linux `script`,
  cron).
- **Secret redaction before write.** Commands and output are run through
  `assets/redaction-patterns.txt` (AWS keys, `KEY=value` secrets, `export SECRET=…`, Bearer/
  Authorization, JWT, `ghp_`/`xoxb-`/`sk-`, PEM headers) → `«redacted»`, with surgical
  capture-group redaction and a built-in default list as a fallback.
- **Private by default.** `~/.recall` is created `chmod 700`; `scan_secrets.sh` (CI) fails if any
  captured artifact is tracked or a credential-shaped value lands in a tracked file.
- Commands: `/recall:setup`, `/recall:list`, `/recall:show`, `/recall:search`, `/recall:resume`,
  `/recall:snapshot`.
- Engine (`scripts/recall.py`, stdlib only): render / snapshot / finalize / list / show / search /
  resume / redact / setup, rendering `sessions/<id>.md` + `index.md`; fast dispatcher
  (`scripts/recall.sh`) with a pure-shell `log` path; shell integrations
  (`scripts/recall.{zsh,bash}`); scheduler installer (`scripts/install-scheduler.sh`) with a
  launchd template.
- Reference docs (architecture, capture, privacy, scheduler), asset templates
  (session + index), and a fictional worked example under `examples/demo-session/`.

### Fixed

- **Progress-bar redraws now collapse.** `clean_typescript` relies on carriage returns to keep
  only the final redraw of a line, but Python's universal-newline translation was rewriting `\r`
  to `\n` on read, so `building: 10%\r…100%` rendered as three lines. The raw typescript is now
  read with newline translation disabled, so it collapses to the final state.
