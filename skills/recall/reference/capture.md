# Capture — how it works, and how it degrades

recall's promise is "works all the time." That's only true because capture is layered: the
command log never depends on the fragile part (output recording), and every fragile step has a
guard and a fallback.

## Layer 1 — command log (always on)

The shell hooks record every command with zero dependency on `script` or a TTY:

- **zsh:** `add-zsh-hook preexec` stashes the command + `EPOCHREALTIME` start; `add-zsh-hook
  precmd` computes the exit code + duration and calls `recall.sh log`.
- **bash:** a `DEBUG` trap stashes `$BASH_COMMAND` + a `date +%s%N` start; `PROMPT_COMMAND` logs
  on completion. (Completions and the prompt command itself are filtered out.)

`recall.sh log` appends one JSON line to `cmd/<id>.jsonl`, encoded in `awk` (escapes `\`, `"`,
`\t`, strips `\r`, joins multi-line commands with `\n`). This is the layer that guarantees you
always get *something*, even in a plain TTY with no `script`.

## Layer 2 — output recording (best effort)

For a full transcript, the integration re-execs your shell under `script` **once** per window:

```sh
# macOS / BSD:
exec script -q "$RECALL_RAW" "$SHELL"
# util-linux (Linux):
exec script -q -f -c "$SHELL" "$RECALL_RAW"
```

The inner shell re-sources the integration with `RECALL_RECORDING=1` already set, so it installs
hooks instead of re-execing again. The re-exec is guarded so it can never wedge a session:

| Guard | Effect |
|---|---|
| `[[ -o interactive ]]` / `case $- in *i*` | non-interactive shells are skipped entirely |
| `RECALL_DISABLE` set | recall does nothing |
| `CI` set / `TERM=dumb` | skipped (build agents, dumb terminals) |
| `RECALL_RECORDING` set | already inside `script` — don't recurse |
| `RECALL_CAPTURE_OUTPUT=0` | opt out of output recording (keep the command log) |
| `RECALL_NO_SCRIPT` set | never use `script` |
| `-t 1` false / no `script` binary | can't record — continue **unrecorded** |

If any guard trips, there is **no transcript**, and the rendered session simply says
`Output capture: off (commands only)`. The command table is unaffected.

## The macOS / Linux `script` divergence

`script`'s flags differ by platform and this bites everyone:

- **macOS / BSD:** `script -q <file> <command…>` — the file is a positional arg, the command
  follows.
- **util-linux (Linux):** `script -q -f -c "<command>" <file>` — the command is a `-c` string,
  the file is positional, and `-f` flushes so the interval snapshot sees output promptly.

The integration branches on `uname -s` to pick the right form.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `RECALL_HOME` | `~/.recall` | where all streams + rendered files live |
| `RECALL_DISABLE` | unset | set to disable recall entirely for a shell |
| `RECALL_CAPTURE_OUTPUT` | `1` | `0` = command log only, never re-exec under `script` |
| `RECALL_NO_SCRIPT` | unset | set to skip `script` (e.g. if it misbehaves in your terminal) |
| `RECALL_SESSION_ID` | `<epoch>-<pid>-<rand>` | stable per-window id (inherited across the re-exec) |
| `RECALL_WINDOW` | terminal/tmux hint | groups a reopened window to its prior session for `resume` |

## Failure modes and what you still get

| If… | You still get… |
|---|---|
| no `script` binary | complete command log, no transcript |
| force-closed (SIGKILL, power loss) | everything up to the last interval snapshot (see `scheduler.md`) |
| a torn last JSONL line from a hard crash | every intact command; the torn line is skipped on read |
| `script` re-exec fails mid-start | the shell continues unrecorded; the command log still records |
| running in CI / a dumb terminal | nothing (by design — recall is for interactive use) |
