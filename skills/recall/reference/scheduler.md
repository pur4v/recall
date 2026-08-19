# Interval snapshotting

The shell exit hook renders a session when a terminal closes **gracefully**. But a force-quit, a
`kill -9`, a panic, or a power loss never fires that hook. The interval snapshotter closes that
gap: it re-renders **all** sessions on a timer, so the worst case is losing only the seconds since
the last tick.

## What it runs

```
recall snapshot   →   render every session from its streams   →   rebuild index.md
```

`snapshot` is idempotent and cheap: it reads `cmd/`, `raw/`, and `meta/` and regenerates
`sessions/*.md` + `index.md`. Running it every N seconds means an ungracefully-closed window is
still captured up to the last N-second boundary.

## Install

```sh
sh scripts/install-scheduler.sh [--interval SECONDS] [--uninstall]
```

Default interval is **300s** (5 min). The installer detects the platform:

### macOS — launchd LaunchAgent

- Substitutes `@CLI@` (the absolute path to `recall.sh`) and `@INTERVAL@` into
  `assets/com.pur4v.recall.plist`, writes it to
  `~/Library/LaunchAgents/com.pur4v.recall.plist`, and `launchctl load`s it.
- `StartInterval @INTERVAL@` runs `recall snapshot` every interval; `RunAtLoad` runs it once on
  load. stdout/stderr go to `/tmp/recall.snapshot.{out,err}`.
- Remove: `sh scripts/install-scheduler.sh --uninstall` (unloads + deletes the plist).

### Linux — crontab

- Adds `*/M * * * * <recall.sh> snapshot >/dev/null 2>&1` where `M = ceil(interval/60)` minutes
  (minimum 1). Existing recall cron lines are replaced, not duplicated.
- Remove: `--uninstall` strips the recall line from the crontab.

## Choosing an interval

| Interval | Trade-off |
|---|---|
| 60s | tightest recovery window; more frequent (still cheap) renders |
| 300s (default) | lose at most ~5 min of an ungracefully-closed window; negligible cost |
| 900s+ | fine if you mostly close terminals gracefully (the exit hook covers those) |

Graceful closes don't need the snapshot at all — the `zshexit` / bash `trap EXIT` hook already
renders them. The snapshot exists purely for the un-graceful case.

## Verifying it's running

- **macOS:** `launchctl list | grep com.pur4v.recall`, and check
  `/tmp/recall.snapshot.out` grows over time.
- **Linux:** `crontab -l | grep recall`.
- **Either:** run `recall list` — after a snapshot, active sessions show current command counts.
