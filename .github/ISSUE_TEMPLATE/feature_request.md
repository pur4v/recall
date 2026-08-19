---
name: Feature request
about: Suggest an improvement to the recall kit
title: "[feat] "
labels: enhancement
---

**The problem**
What's hard or missing today?

**Proposed change**
What should recall do instead? Which part does it touch (capture / render / scheduler / command /
redaction)?

**Fits the principles?**
- [ ] Keeps "kit = tooling, data = yours" (no captured data in the repo)
- [ ] Redaction still runs before any write; store stays private (`chmod 700`)
- [ ] Hot path stays pure-shell (no per-command interpreter spawn)
- [ ] Capture still degrades gracefully (commands-only fallback)

**Alternatives considered**
