# Example — a captured recall session

A **fictional** worked example of what recall writes into `$RECALL_HOME` (default `~/.recall`).
These are the *rendered outputs* only; the real low-level streams (`cmd/*.jsonl`, `raw/*.log`,
`meta/*.json`) live in `~/.recall` and are never committed.

| File | What it is |
|---|---|
| [`1755590400-4321-8842.md`](1755590400-4321-8842.md) | one rendered session — metadata table, command table, and cleaned output transcript |
| [`index.md`](index.md) | the session index (all sessions, newest first) |

## What to notice

- **Redaction happened before write.** `export API_KEY=«redacted»`, the `Bearer «redacted»` in
  the `curl`, and `AWS_SECRET_ACCESS_KEY=«redacted»` in the *output* are all masked — recall
  redacts both the command log and the transcript (`skills/recall/reference/privacy.md`).
- **Non-zero exits are flagged.** `npm run build` exited `1 ⚠️`.
- **Progress redraws collapse.** The build printed `building: 10%\r…55%\r…100%`; the transcript
  shows only the final `building: 100%` (`clean_typescript` keeps the last redraw of a line).
- **The window hint** (`w0t1p0:AF39-demo`) is how `recall resume` reconnects a reopened terminal
  to its prior session.

This example is regenerable: the same streams fed to `recall finalize` / `recall snapshot` produce
exactly these files.
