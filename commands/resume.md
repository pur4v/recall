---
description: Reprint the last session's directory and recent commands to pick up where you left off
argument-hint: "[session-id] [--window] [-n N]"
---

Recover context from a previous terminal session — for when a terminal was closed (or crashed)
and you want to continue exactly where you were.

Target: `$1` (default: the most recent session; with `--window`, the prior session for *this*
terminal window).

1. Run `python3 skills/recall/scripts/recall.py resume ${1:+$1} ${2:-} -n ${N:-10}`. It prints
   the session's start time, window, **last working directory** (with a ready-to-run `cd`), the
   last N commands, and the path to the full rendered log.
2. Offer the user the `cd` back to that directory, and summarize what they were mid-way through
   (the recent commands, any that failed with a non-zero exit).
3. If there's no previous session, say so and suggest `/recall:list`.

This reads captured history only — it does not replay or re-run any command.
