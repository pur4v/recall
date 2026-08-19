---
description: Install the recall shell integration and the interval snapshotter
argument-hint: "[--apply] [--interval SECONDS]"
---

Set up the **recall** skill so this machine starts capturing terminal session history.

1. Show the install steps (dry run): `python3 skills/recall/scripts/recall.py setup --interval ${2:-300}`.
   This prints the exact `source …/recall.{zsh,bash}` line for your shell rc and the scheduler
   command — nothing is changed yet.
2. If the user passed `--apply` (`$1`), run `recall.py setup --apply --interval ${2:-300}` to append
   the `source` line to `~/.zshrc` (idempotent — skipped if already present), then install the
   interval snapshotter: `sh skills/recall/scripts/install-scheduler.sh --interval ${2:-300}`
   (launchd on macOS, cron on Linux — see `reference/scheduler.md`).
3. Tell the user to **open a new terminal** — capture starts automatically. Explain the privacy
   posture briefly: history lives in `~/.recall` (chmod 700), secrets are redacted before write,
   and nothing captured is ever committed (`reference/privacy.md`).
4. Note the opt-outs: `RECALL_DISABLE=1` (off entirely), `RECALL_CAPTURE_OUTPUT=0` (command log
   only, no output transcript), `RECALL_NO_SCRIPT=1` (skip `script`). See `reference/capture.md`.

Report what was changed (rc file + scheduler) or, on a dry run, exactly what *would* change.
