# Contributing to recall

Thanks for your interest. recall is a Claude skill + Claude Code plugin — a **kit**, not a data
store. Keep that boundary: the repo holds scripts, commands, references, and templates; it must
**never** contain captured session data.

## Ground rules

- **Kit = tooling, data = yours.** No captured sessions in the repo. Examples are fictional and
  marked as such.
- **Redaction first.** Anything written to a rendered session passes through the redaction
  patterns. If you add a capture path, redact before write.
- **Private by default.** `~/.recall` is `chmod 700`; nothing captured is ever committed. Run
  `npm run scan-secrets` (or `sh skills/recall/scripts/scan_secrets.sh .`) before every commit.
- **No prompt latency.** Keep the per-command hot path in pure shell — no interpreter spawn per
  command. Expensive work belongs in `recall.py`, run out of band.
- **Degrade, never fail.** Output capture is best-effort; every fragile step needs a guard and a
  commands-only fallback.

## Before you open a PR

1. `python3 -m py_compile skills/recall/scripts/recall.py` — must pass.
2. `sh -n` every `skills/recall/scripts/*.sh`; `bash -n skills/recall/scripts/recall.bash`;
   `zsh -n skills/recall/scripts/recall.zsh` (if zsh is available).
3. Validate JSON — `.claude-plugin/*.json` and `package.json` must parse.
4. `npm run scan-secrets` — clean; no secrets or captured data committed.
5. Keep `SKILL.md` frontmatter valid (`name` + `description`) and each command's frontmatter with
   `description` + `argument-hint`.
6. If you change rendering, confirm the example still matches: feed the streams to
   `recall finalize` and diff against `examples/demo-session/`.

## Style

Match the surrounding docs: tight prose, tables over walls of text, and an honest description of
what degrades and when.

## Commits

Use clear, imperative messages. CI runs the same checks listed above.
