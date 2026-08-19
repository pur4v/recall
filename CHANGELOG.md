# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/); this project adheres to
[Semantic Versioning](https://semver.org/).

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
