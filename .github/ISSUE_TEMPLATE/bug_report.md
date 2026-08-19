---
name: Bug report
about: Something in the recall kit (a script, command, integration, or reference) doesn't work as documented
title: "[bug] "
labels: bug
---

**What happened**
A clear description of the bug.

**Which part of the kit**
- [ ] a command (`/recall:...`)
- [ ] a shell integration (recall.zsh / recall.bash)
- [ ] the render engine (recall.py / recall.sh)
- [ ] the scheduler (install-scheduler.sh / launchd / cron)
- [ ] redaction (patterns / secret leaked into a render)
- [ ] a reference doc / template

**Steps to reproduce**
1.
2.

**Expected vs actual**

**Environment**
- OS (macOS / Linux distro):
- Shell + version (zsh / bash):
- Terminal (iTerm / Terminal / tmux / …):
- `script` available? (`command -v script`):

**Note:** do NOT paste secrets or real captured session content. If reporting a redaction miss,
share the *pattern* of the value (e.g. `sk-` prefix, 40 chars), not the value itself.
