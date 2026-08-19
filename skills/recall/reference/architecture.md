# Architecture

recall is split into a **cheap capture path** (shell, always-on, no interpreter spawn on the hot
path) and an **expensive render path** (Python, out of band). Nothing on the render path can slow
down your prompt; nothing on the capture path can lose a command.

## The files

Everything lives under `$RECALL_HOME` (default `~/.recall`), created `chmod 700`:

```
~/.recall/
  cmd/<id>.jsonl     one JSON record per command  (ts, exit, dur_ms, cwd, cmd)
  raw/<id>.log       the raw `script` typescript   (full output, when capture is on)
  meta/<id>.json     session metadata              (started, ended, host, shell, tty, window)
  sessions/<id>.md   rendered, redacted transcript (the human-readable artifact)
  index.md           all sessions, newest first
```

The session **`<id>`** is `"$(date +%s)-$$-$RANDOM"`, assigned once per terminal and inherited
across the `script` re-exec so a window keeps one id for its whole life.

## The pieces

| File | Role |
|---|---|
| `scripts/recall.zsh` | zsh integration: guards → set session env → re-exec under `script` once → register hooks (`preexec`/`precmd`/`zshexit`) |
| `scripts/recall.bash` | bash integration: same idea via `DEBUG` trap + `PROMPT_COMMAND` + `trap EXIT` |
| `scripts/recall.sh` | fast POSIX dispatcher. `log` is pure shell (awk JSON-encode); everything else `exec`s `recall.py` |
| `scripts/recall.py` | render + query engine (stdlib only): begin / finalize / render / snapshot / list / show / search / resume / redact / setup |
| `scripts/install-scheduler.sh` | install/remove the interval snapshotter (launchd on macOS, cron on Linux) |
| `scripts/scan_secrets.sh` | CI guard: no captured artifacts tracked, no credential-shaped values in tracked files |
| `assets/redaction-patterns.txt` | one Python regex per line; applied to commands *and* output before write |
| `assets/com.pur4v.recall.plist` | launchd template (`@CLI@`, `@INTERVAL@` substituted by the installer) |

## The two paths

### Capture (hot, shell-only)

1. On shell start, the integration sets the session env and (once) re-execs the shell under
   `script` for output capture, then calls `recall begin` to write `meta/<id>.json`.
2. Before each command, the hook records the command line + a start timestamp.
3. After the command, the hook calls `recall.sh log <exit> <dur_ms> <cwd> -- <cmd>`, which
   appends one JSON line to `cmd/<id>.jsonl` **in pure shell** — no Python process per command.
4. On shell exit, `recall finalize` stamps `ended`, renders the session, and rebuilds the index.

### Render (cold, Python)

`recall.py` reads the three streams for a session and produces `sessions/<id>.md`:

- **Command table** — time, dir (abbreviated to `~`), command, exit (with ⚠️ when non-zero),
  duration. Each command is redacted first.
- **Transcript** — the raw typescript, cleaned by `clean_typescript()` (normalize CRLF, collapse
  carriage-return redraws so a progress bar shows its final state, strip ANSI CSI/OSC/other +
  control chars, drop the `Script started/done` header/footer), then redacted.
- **Metadata table** — started/ended, host, shell, tty, window, command count, last dir, and
  whether output capture was on.

`rebuild_index()` summarizes every session (from `meta` + `cmd`) into `index.md`, newest first.

## Why this shape

- **No prompt latency.** The per-command write never spawns an interpreter — it's `awk` inside a
  short-lived `recall.sh` invocation. Rendering is deferred to exit or the interval snapshot.
- **Crash-proof capture.** `cmd/<id>.jsonl` is append-only; a torn trailing line from a hard
  crash is skipped on read. `meta` is written atomically (temp + `os.replace`). The rendered
  `.md` is fully regenerable from the streams at any time.
- **Idempotent rendering.** `render`, `snapshot`, and `finalize` can run any number of times and
  in any order (exit hook + interval scheduler + manual `show`) — they always reproduce the same
  artifact from the streams.
