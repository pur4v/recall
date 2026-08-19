## What this changes

Brief description of the change and which part it touches (a command, a shell integration, the
render engine, the scheduler, a reference, or a template).

## Checklist

- [ ] `python3 -m py_compile skills/recall/scripts/recall.py` passes
- [ ] `sh -n` on `*.sh`, `bash -n recall.bash`, `zsh -n recall.zsh` (if available) pass
- [ ] All JSON parses (`.claude-plugin/*.json`, `package.json`)
- [ ] `npm run scan-secrets` is clean; no secrets or captured session data committed
- [ ] `SKILL.md` frontmatter valid; each command has `description` + `argument-hint`
- [ ] If rendering changed, `examples/demo-session/` still matches a round-trip
- [ ] Hot path stays pure-shell (no interpreter spawn per command); output capture still degrades
      to commands-only
- [ ] Redaction runs before any write; `~/.recall` stays `chmod 700`

## Notes
