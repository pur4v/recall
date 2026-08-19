# Privacy & redaction

recall records what you type and what your terminal prints. That is inherently sensitive, so the
default posture is defensive: **redact before writing, keep the store private, never commit
captured data.**

## Redaction

Every command line and every line of output passes through the patterns in
`assets/redaction-patterns.txt` **before** it is written to a `sessions/<id>.md`. The matched
secret is replaced with `«redacted»`.

- **One Python regex per line;** `#` comments and blank lines are ignored.
- **Capture groups are surgical:** if a pattern has capture groups, only the group text is
  redacted (surrounding context is kept — e.g. `export API_KEY=«redacted»`). A pattern with no
  groups has its whole match redacted.
- If the patterns file is missing or empty, `recall.py` falls back to a built-in default list, so
  redaction never silently turns off.

Shipped patterns cover:

| Pattern | Example it catches |
|---|---|
| AWS access key id | `AKIA...` (16 upper/digit) |
| `aws_secret_access_key = …` | the secret value |
| generic `KEY=value` / `KEY: value` | `password`, `secret`, `token`, `api_key`, `access_key`, `private_key`, `client_secret`, `auth_token` |
| `export SECRET=…` | `export DB_PASSWORD=…` |
| Bearer / Authorization headers | `Authorization: Bearer <token>` |
| JWT | `eyJ….eyJ….<sig>` |
| provider tokens | `ghp_…`, `gho_…`, `xoxb-…`, `sk-…` |
| PEM private key header | a `BEGIN … PRIVATE KEY` marker line |

**Add your own.** Append a regex to `redaction-patterns.txt`; it takes effect on the next render.
Re-render already-captured sessions with `recall snapshot` after adding a pattern.

### Redaction is a floor, not a guarantee

Regexes can't catch every secret shape. If output *might* contain something sensitive that no
pattern matches, treat the session as sensitive regardless. The mitigations below assume redaction
is imperfect.

## The store is private

- `~/.recall` is created **`chmod 700`** (owner-only). Only your user can read the captured
  history.
- Captured data lives **only** under `$RECALL_HOME` — never in this skill repo, never in a project
  repo, never in a commit.

## Never committed — enforced in CI

`scripts/scan_secrets.sh` runs in CI (and via `npm run scan-secrets`) and **fails the build** if:

- any captured-session artifact is tracked by git — anything matching `.recall/`, `*.log`,
  `*.jsonl`, `raw/`, or `sessions/*.md`; or
- a credential-shaped value (AWS key, PEM header, `ghp_`/`xoxb-` token, JWT) appears in a tracked
  file (the redaction-patterns file and the scanner itself are excluded, since they legitimately
  contain pattern fragments).

`.gitignore` also excludes `.recall/`, `*.log`, `*.jsonl`, and `sessions/` as defense in depth.

## Turning it off

- Per shell: `export RECALL_DISABLE=1` before the integration is sourced.
- Command log only (no output transcript): `export RECALL_CAPTURE_OUTPUT=0`.
- Delete a session: remove its files under `~/.recall/{cmd,raw,meta,sessions}/<id>.*` and re-run
  `recall snapshot` to rebuild the index. Delete everything with `rm -rf ~/.recall`.

## What recall never does

- It never sends captured data anywhere — there is no network code in the kit.
- It never writes captured data into a repository.
- It never runs in CI or non-interactive shells (guarded by `CI` / `TERM=dumb` / interactive
  checks), so it won't capture build secrets.
