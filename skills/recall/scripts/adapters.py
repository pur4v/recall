#!/usr/bin/env python3
"""recall adapters — import conversation transcripts from AI CLI agents into one normalized form.

recall stores the *entire* context of a working session, not just the shell: alongside the command
log and output transcript, it ingests the **conversation** you had with whatever AI CLI agent you
ran in that terminal. Each agent stores its history differently, so an adapter per agent turns that
native format into a common shape:

    {
      "agent":   "claude-code",          # which tool produced it
      "conv_id": "<stable id>",           # unique per conversation
      "cwd":     "/abs/path",             # where the agent ran (used to correlate to a session)
      "source":  "/abs/path/to/native",   # the file it came from
      "started": <epoch>, "ended": <epoch>,
      "turns":   [ {"ts": <epoch>, "role": "user|assistant", "text": "..."} , ... ],
    }

Adding an agent = one function that yields those dicts, registered in ADAPTERS. Everything is
stdlib-only and degrades gracefully: an agent whose store is absent simply contributes nothing.
Redaction happens later, in recall.py, before anything is written to Markdown.
"""

import glob
import json
import os
from datetime import datetime


# --------------------------------------------------------------------------- helpers


def iso_to_epoch(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def _blocks_to_text(content, include_thinking=True):
    """Flatten a message's content (a plain string, or a list of typed blocks) to readable text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return str(content).strip()
    parts = []
    for b in content:
        if isinstance(b, str):
            parts.append(b)
            continue
        if not isinstance(b, dict):
            parts.append(str(b))
            continue
        t = b.get("type")
        if t == "text":
            parts.append(b.get("text", ""))
        elif t == "thinking":
            if include_thinking and b.get("thinking"):
                parts.append("[thinking] " + b["thinking"])
        elif t == "tool_use":
            inp = b.get("input", {})
            try:
                inp = json.dumps(inp, ensure_ascii=False)
            except (TypeError, ValueError):
                inp = str(inp)
            parts.append("[tool: %s] %s" % (b.get("name", "?"), inp[:800]))
        elif t == "tool_result":
            parts.append("[tool result] " + _blocks_to_text(b.get("content"), include_thinking))
        elif t in ("image", "attachment"):
            parts.append("[%s]" % t)
    return "\n".join(p for p in parts if p and p.strip()).strip()


# --------------------------------------------------------------------------- claude-code


def _claude_home():
    return os.environ.get("CLAUDE_HOME", os.path.expanduser("~/.claude"))


def claude_code_conversations(**_):
    """Claude Code writes one JSONL per session under ~/.claude/projects/<cwd-slug>/<uuid>.jsonl.
    Each user/assistant record carries `cwd`, `timestamp`, and a `message` with typed content."""
    base = os.path.join(_claude_home(), "projects")
    include_thinking = os.environ.get("RECALL_INCLUDE_THINKING", "1") != "0"
    out = []
    for path in glob.glob(os.path.join(base, "*", "*.jsonl")):
        conv = _parse_claude_file(path, include_thinking)
        if conv:
            out.append(conv)
    return out


def _parse_claude_file(path, include_thinking):
    turns, cwd, started, ended, title = [], None, None, None, None
    conv_id = os.path.splitext(os.path.basename(path))[0]
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return None
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue  # a torn line — skip it
            if d.get("cwd") and not cwd:
                cwd = d.get("cwd")
            if d.get("type") == "ai-title" and d.get("aiTitle"):
                title = d["aiTitle"]  # Claude Code's own summary of the conversation; last wins
            if d.get("type") not in ("user", "assistant"):
                continue
            m = d.get("message") or {}
            text = _blocks_to_text(m.get("content"), include_thinking)
            if not text:
                continue
            ts = iso_to_epoch(d.get("timestamp"))
            if ts is not None:
                started = ts if started is None else min(started, ts)
                ended = ts if ended is None else max(ended, ts)
            turns.append({"ts": ts, "role": m.get("role") or d.get("type"), "text": text})
    if not turns:
        return None
    return {
        "agent": "claude-code",
        "conv_id": conv_id,
        "cwd": cwd,
        "source": path,
        "title": title,
        "started": started,
        "ended": ended,
        "turns": turns,
    }


# --------------------------------------------------------------------------- aider


def aider_conversations(cwds=None, **_):
    """aider keeps a per-project `.aider.chat.history.md` in the repo root. We can't scan the whole
    disk, so we look in the cwds recall already knows about (from captured terminal sessions)."""
    out, seen = [], set()
    for cwd in cwds or []:
        if not cwd:
            continue
        p = os.path.join(cwd, ".aider.chat.history.md")
        rp = os.path.realpath(p)
        if rp in seen or not os.path.isfile(p):
            continue
        seen.add(rp)
        conv = _parse_aider(p, cwd)
        if conv:
            out.append(conv)
    return out


def _parse_aider(path, cwd):
    turns = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
    except OSError:
        return None
    role, buf = "assistant", []

    def flush():
        text = "\n".join(buf).strip()
        if text:
            turns.append({"ts": None, "role": role, "text": text})

    for line in raw.splitlines():
        if line.startswith("#### "):  # aider marks user prompts with a #### heading
            flush()
            buf = [line[5:]]
            role = "user"
        elif line.startswith("# aider chat started"):
            flush()
            buf, role = [], "assistant"
        else:
            if role == "user" and line.strip() == "":
                flush()
                buf, role = [], "assistant"
            else:
                buf.append(line)
    flush()
    if not turns:
        return None
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None
    first_user = next((t["text"] for t in turns if t["role"] == "user"), "")
    return {
        "agent": "aider",
        "conv_id": "aider-" + os.path.basename(os.path.dirname(os.path.realpath(path)) or "root"),
        "cwd": cwd,
        "source": path,
        "title": first_user.splitlines()[0][:80] if first_user else None,
        "started": None,
        "ended": mtime,
        "turns": turns,
    }


# --------------------------------------------------------------------------- registry


ADAPTERS = {
    "claude-code": claude_code_conversations,
    "aider": aider_conversations,
}


def enabled_agents():
    raw = os.environ.get("RECALL_AGENTS", "claude-code,aider")
    return [a.strip() for a in raw.split(",") if a.strip() in ADAPTERS]


def discover(cwds=None):
    """Run every enabled adapter and return all normalized conversations, newest activity first."""
    convs = []
    for agent in enabled_agents():
        try:
            convs.extend(ADAPTERS[agent](cwds=cwds) or [])
        except Exception:  # noqa: BLE001 — an adapter must never break the whole ingest
            continue
    convs.sort(key=lambda c: (c.get("ended") or c.get("started") or 0), reverse=True)
    return convs


if __name__ == "__main__":
    for c in discover():
        print("%-12s %-40s turns=%-4d cwd=%s" % (c["agent"], c["conv_id"], len(c["turns"]), c["cwd"]))
