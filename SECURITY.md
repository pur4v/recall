# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Instead, report privately via GitHub
Security Advisories ("Report a vulnerability" on the repo's Security tab). Include steps to
reproduce and any relevant context. You'll get an acknowledgment as soon as possible.

## Scope

recall captures terminal commands and output — inherently sensitive data — so its security posture
is central, not incidental:

- **Redaction.** Commands and output are run through `assets/redaction-patterns.txt` before being
  written to disk. This is a heuristic floor, not a guarantee — report patterns that miss common
  secret shapes, or ways redaction can be bypassed.
- **Store privacy.** `~/.recall` is created `chmod 700`. Report anything that could widen those
  permissions or expose captured data to other users.
- **No exfiltration.** The kit contains no network code and never transmits captured data. Report
  anything that would send captured data anywhere.
- **No committed data.** `scan_secrets.sh` (CI) fails if captured artifacts or credential-shaped
  values are tracked. Report gaps in its patterns.
- **The shell integration.** It re-execs the shell under `script`; report any way it could wedge a
  session, run untrusted input, or leak credentials.

## Not in scope

- Secrets that a user pastes into their terminal that no redaction pattern could reasonably match
  (redaction is best-effort; treat captured sessions as sensitive regardless).
- Vulnerabilities in `script`, launchd, cron, or the shell itself (report those upstream).

## Hardening tips for users

- Keep `~/.recall` on an encrypted volume; it is `chmod 700` but not itself encrypted.
- Use `RECALL_CAPTURE_OUTPUT=0` to keep only the command log, or `RECALL_DISABLE=1` to turn recall
  off, in shells where you handle highly sensitive output.
- Add your own patterns to `redaction-patterns.txt` and re-run `recall snapshot` to re-redact.
