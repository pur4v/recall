#!/usr/bin/env python3
"""recall.py — render and query captured terminal sessions.

The shell integration writes two low-level streams per session under $RECALL_HOME:

    cmd/<id>.jsonl   one JSON record per command (ts, exit, dur_ms, cwd, cmd)
    raw/<id>.log     the raw `script` typescript (full output), when output capture is on
    meta/<id>.json   session metadata (start/end, host, shell, tty, window)

This tool turns those into a clean, human-readable, **secret-redacted** Markdown file per
session (`sessions/<id>.md`) plus an `index.md`, and answers list/show/search/resume queries.
Stdlib only; runs on macOS and Linux. The per-command `log` write is done in shell
(`recall.sh`) for speed — this file handles everything else.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adapters  # noqa: E402 — sibling module, same scripts/ dir

REDACTION = "«redacted»"


# --------------------------------------------------------------------------- paths


def home():
    return os.environ.get("RECALL_HOME", os.path.expanduser("~/.recall"))


def _p(*parts):
    return os.path.join(home(), *parts)


def ensure_dirs():
    for d in ("raw", "cmd", "meta", "sessions", "conv", "conversations", "diff"):
        os.makedirs(_p(d), exist_ok=True)
    # captured history is sensitive — keep the tree private.
    try:
        os.chmod(home(), 0o700)
    except OSError:
        pass


def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------- io helpers


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def read_text(path, newline=None):
    # newline="" disables universal-newline translation so raw `script` typescripts keep their
    # carriage returns — clean_typescript() needs them to collapse progress-bar redraws.
    try:
        with open(path, encoding="utf-8", errors="replace", newline=newline) as fh:
            return fh.read()
    except OSError:
        return ""


def now_iso():
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def read_cmds(sid):
    out = []
    for line in read_text(_p("cmd", sid + ".jsonl")).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            pass  # a torn trailing line from a crash — skip it
    return out


# --------------------------------------------------------------------------- redaction


_DEFAULT_PATTERNS = [
    r"\b(AKIA[0-9A-Z]{16})\b",
    r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
    r"private[_-]?key|client[_-]?secret|auth[_-]?token)\b\s*[=:]\s*(\"[^\"]*\"|'[^']*'|\S+)",
    r"(?i)\bexport\s+\w*(?:password|secret|token|key)\w*=(\"[^\"]*\"|'[^']*'|\S+)",
    r"(?i)\b(?:bearer|authorization:?)\s+([A-Za-z0-9._~+/-]{12,}=*)",
    r"\b(eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})\b",
    r"\b(gh[pousr]_[A-Za-z0-9]{20,})\b",
    r"\b(xox[baprs]-[A-Za-z0-9-]{10,})\b",
    r"\b(sk-[A-Za-z0-9]{20,})\b",
    r"-----BEGIN[^-]*PRIVATE KEY-----",
]


def load_patterns():
    path = os.path.join(_script_dir(), "..", "assets", "redaction-patterns.txt")
    lines = []
    raw = read_text(path)
    if raw:
        for line in raw.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    if not lines:
        lines = _DEFAULT_PATTERNS
    compiled = []
    for pat in lines:
        try:
            compiled.append(re.compile(pat))
        except re.error:
            pass
    return compiled


def _redact_match(match):
    """Redact every capture group in the match (preserving surrounding text); if the pattern
    has no groups, redact the whole match."""
    groups = match.groups()
    if not groups:
        return REDACTION
    whole = match.group(0)
    base = match.start(0)
    spans = sorted(
        (match.start(i), match.end(i))
        for i in range(1, len(groups) + 1)
        if match.group(i) is not None
    )
    out, last = [], 0
    for a, b in spans:
        out.append(whole[last : a - base])
        out.append(REDACTION)
        last = b - base
    out.append(whole[last:])
    return "".join(out)


def redact(text, patterns):
    for rx in patterns:
        text = rx.sub(_redact_match, text)
    return text


# --------------------------------------------------------------------------- typescript cleaning


_ANSI_OSC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_ANSI_CSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_ANSI_OTHER = re.compile(r"\x1b[@-Z\\-_]")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_SCRIPT_HDR = re.compile(r"^Script (started|done)")


def clean_typescript(raw):
    """Turn a raw `script` typescript into readable plain text: normalize line endings,
    collapse carriage-return redraws (progress bars), strip ANSI/control sequences, and drop
    the script header/footer lines."""
    out = []
    for line in raw.replace("\r\n", "\n").split("\n"):
        if "\r" in line:
            line = line.split("\r")[-1]  # keep only the final redraw of the line
        line = _ANSI_OSC.sub("", line)
        line = _ANSI_CSI.sub("", line)
        line = _ANSI_OTHER.sub("", line)
        line = _CTRL.sub("", line)
        if _SCRIPT_HDR.match(line):
            continue
        out.append(line)
    while out and out[-1].strip() == "":
        out.pop()
    return "\n".join(out)


# --------------------------------------------------------------------------- formatting


def abbrev(path):
    h = os.path.expanduser("~")
    if path and path.startswith(h):
        return "~" + path[len(h) :]
    return path or ""


def hhmmss(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%H:%M:%S")
    except (ValueError, OSError, OverflowError):
        return "??:??:??"


def hhmmss_date(ts):
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError, OverflowError, TypeError):
        return "?"


def iso_epoch(s):
    """Parse recall's own ISO timestamps (now_iso format, with tz offset) to epoch seconds."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s)).timestamp()
    except (ValueError, TypeError):
        try:
            return datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S").timestamp()
        except (ValueError, TypeError):
            return None


def fmt_dur(ms):
    try:
        ms = int(ms)
    except (ValueError, TypeError):
        return ""
    if ms < 1000:
        return "%dms" % ms
    s = ms / 1000.0
    if s < 60:
        return "%.1fs" % s
    return "%dm%ds" % (int(s) // 60, int(s) % 60)


def cell(text):
    return (text or "").replace("|", "\\|").replace("\n", " ⏎ ")


# --------------------------------------------------------------------------- titles & slugs


_COMMON_CMDS = {"ls", "cd", "clear", "pwd", "ll", "cat", "exit", "vim", "vi", "code", "echo"}


def slugify(text, maxlen=60):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return (s[:maxlen].rstrip("-")) or "session"


def short_id(sid):
    return hashlib.sha1(sid.encode("utf-8")).hexdigest()[:6]


def derive_title(meta, cmds, conv_title=None):
    """A human title describing what a session was about. Prefer the AI conversation's own title;
    else the repo/last-dir plus the most distinctive commands run."""
    if conv_title:
        return conv_title.strip()
    scope = ""
    gs = meta.get("git_start") or {}
    if gs.get("root"):
        scope = os.path.basename(gs["root"])
    elif cmds:
        scope = os.path.basename((cmds[-1].get("cwd") or "").rstrip("/"))
    verbs = []
    for c in cmds:
        head = (c.get("cmd") or "").strip().split()
        if head and head[0] not in _COMMON_CMDS and head[0] not in verbs:
            verbs.append(head[0])
        if len(verbs) >= 3:
            break
    if scope and verbs:
        return "%s: %s" % (scope, ", ".join(verbs))
    if scope:
        return scope
    if verbs:
        return ", ".join(verbs)
    return "terminal session"


def render_filename(sid, title):
    return "%s--%s.md" % (slugify(title), short_id(sid))


# --------------------------------------------------------------------------- git & env context


def _git(cwd, *args):
    if not cwd:
        return None
    try:
        r = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def git_state(cwd):
    root = _git(cwd, "rev-parse", "--show-toplevel")
    if not root:
        return None
    return {
        "root": root,
        "branch": _git(cwd, "rev-parse", "--abbrev-ref", "HEAD"),
        "head": _git(cwd, "rev-parse", "HEAD"),
        "dirty": bool(_git(cwd, "status", "--porcelain")),
    }


def git_context(meta):
    """Compute what changed in the repo since the session began: commits made, files touched, diff."""
    gs = meta.get("git_start") or {}
    root = gs.get("root")
    if not root or not os.path.isdir(root):
        return None
    start = gs.get("head")
    end = _git(root, "rev-parse", "HEAD")
    commits = []
    if start and end and start != end:
        log = _git(root, "log", "--pretty=%h %s", "%s..%s" % (start, end))
        commits = log.splitlines() if log else []
    base = start or "HEAD"
    numstat = _git(root, "diff", "--numstat", base) or ""
    changed = []
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            changed.append({"added": parts[0], "removed": parts[1], "path": parts[2]})
    diff = _git(root, "diff", base) or ""
    return {
        "root": root,
        "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "start_head": start,
        "end_head": end,
        "dirty": bool(_git(root, "status", "--porcelain")),
        "commits": commits,
        "changed": changed,
        "diff": diff,
    }


_ENV_ALLOW = (
    "SHELL", "TERM", "LANG", "USER", "VIRTUAL_ENV", "CONDA_DEFAULT_ENV",
    "NVM_BIN", "PYENV_VERSION", "NODE_ENV", "AWS_PROFILE", "KUBECONFIG",
)


def capture_env():
    return {k: os.environ[k] for k in _ENV_ALLOW if os.environ.get(k)}


def cwd_trail(cmds):
    trail, seen = [], set()
    for c in cmds:
        d = c.get("cwd")
        if d and d not in seen:
            seen.add(d)
            trail.append(d)
    return trail


# --------------------------------------------------------------------------- conversations


def _conv_key(conv):
    return "%s__%s" % (conv["agent"], re.sub(r"[^A-Za-z0-9._-]+", "-", conv["conv_id"]))


def render_conversation(conv, patterns=None):
    """Write a full, redacted transcript for one AI conversation, plus a cached descriptor used to
    correlate it to terminal sessions. Returns the descriptor (turns stripped)."""
    if patterns is None:
        patterns = load_patterns()
    ensure_dirs()
    key = _conv_key(conv)
    title = conv.get("title") or (conv["turns"][0]["text"].splitlines()[0][:80] if conv["turns"] else key)
    fname = "%s--%s.md" % (slugify(title), short_id(key))

    lines = ["# Conversation — %s" % redact(title, patterns), ""]
    lines += ["| | |", "|---|---|"]
    lines.append("| Agent | %s |" % conv["agent"])
    lines.append("| Conversation id | `%s` |" % conv["conv_id"])
    lines.append("| Working dir | `%s` |" % abbrev(conv.get("cwd") or ""))
    lines.append("| Started | %s |" % (hhmmss_date(conv.get("started")) if conv.get("started") else "?"))
    lines.append("| Ended | %s |" % (hhmmss_date(conv.get("ended")) if conv.get("ended") else "?"))
    lines.append("| Turns | %d |" % len(conv["turns"]))
    lines.append("| Source | `%s` |" % abbrev(conv.get("source") or ""))
    lines.append("")
    lines.append("## Transcript")
    lines.append("")
    for t in conv["turns"]:
        who = "🧑 user" if t["role"] == "user" else "🤖 assistant"
        stamp = hhmmss(t["ts"]) if t.get("ts") else ""
        lines.append("### %s %s" % (who, stamp))
        lines.append("")
        lines.append(redact(t["text"], patterns))
        lines.append("")
    lines.append("---")
    lines.append("_Rendered by recall at %s. Secrets redacted as `%s`._" % (now_iso(), REDACTION))
    lines.append("")
    with open(_p("conversations", fname), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    desc = {
        "agent": conv["agent"], "conv_id": conv["conv_id"], "key": key,
        "cwd": conv.get("cwd"), "title": title, "source": conv.get("source"),
        "started": conv.get("started"), "ended": conv.get("ended"),
        "turns": len(conv["turns"]), "render_file": fname,
    }
    write_json(_p("conv", key + ".json"), desc)
    return desc


def load_conv_descriptors():
    out = []
    for path in glob.glob(_p("conv", "*.json")):
        d = read_json(path)
        if d:
            out.append(d)
    return out


def _overlaps(a0, a1, b0, b1):
    if None in (a0, a1) or None in (b0, b1):
        return False
    return a0 <= b1 and b0 <= a1


def correlate_conversations(meta, cmds):
    """Conversations that ran in this terminal: same dir (or repo) and overlapping time window."""
    started = iso_epoch(meta.get("started"))
    ended = iso_epoch(meta.get("ended")) or time.time()
    dirs = set(cwd_trail(cmds))
    if meta.get("last_cwd"):
        dirs.add(meta["last_cwd"])
    root = (meta.get("git_start") or {}).get("root")
    hits = []
    for d in load_conv_descriptors():
        cwd = d.get("cwd") or ""
        same_place = cwd in dirs or (root and cwd.startswith(root))
        if same_place and _overlaps(started, ended, d.get("started"), d.get("ended")):
            hits.append(d)
    hits.sort(key=lambda d: d.get("started") or 0)
    return hits


def all_known_cwds():
    dirs = set()
    for sid in all_session_ids():
        for c in read_cmds(sid):
            if c.get("cwd"):
                dirs.add(c["cwd"])
        m = read_json(_p("meta", sid + ".json")) or {}
        if m.get("last_cwd"):
            dirs.add(m["last_cwd"])
        root = (m.get("git_start") or {}).get("root")
        if root:
            dirs.add(root)
    return dirs


# --------------------------------------------------------------------------- render


def render_session(sid, patterns=None):
    if patterns is None:
        patterns = load_patterns()
    ensure_dirs()
    meta = read_json(_p("meta", sid + ".json")) or {"id": sid}
    cmds = read_cmds(sid)
    raw = read_text(_p("raw", sid + ".log"), newline="")

    last_cwd = cmds[-1]["cwd"] if cmds else meta.get("last_cwd", "")
    meta["last_cwd"] = last_cwd
    meta["commands"] = len(cmds)

    # Correlate AI conversations that ran in this terminal, and compute git/context.
    convs = correlate_conversations(meta, cmds)
    gctx = git_context(meta)
    trail = cwd_trail(cmds)

    # A meaningful title (prefer the correlated conversation's own summary) drives the filename,
    # so the file itself tells you what the session was about — not an opaque id.
    conv_title = convs[0].get("title") if convs else None
    title = meta.get("title_locked") or derive_title(meta, cmds, conv_title)
    meta["title"] = title
    fname = render_filename(sid, title)
    meta["render_file"] = fname

    lines = []
    lines.append("# %s" % title)
    lines.append("")
    lines.append("> Terminal session `%s`" % sid)
    lines.append("")
    status = "ended %s" % meta["ended"] if meta.get("ended") else "**active**"
    lines.append("| | |")
    lines.append("|---|---|")
    lines.append("| Title | %s |" % cell(title))
    lines.append("| Terminal id | `%s` |" % sid)
    lines.append("| Started | %s |" % meta.get("started", "?"))
    lines.append("| Status | %s |" % status)
    lines.append("| Host | %s |" % meta.get("host", "?"))
    lines.append("| Shell | %s |" % meta.get("shell", "?"))
    lines.append("| TTY | %s |" % meta.get("tty", "?"))
    if meta.get("window"):
        lines.append("| Window | `%s` |" % meta["window"])
    lines.append("| Commands | %d |" % len(cmds))
    lines.append("| Last dir | `%s` |" % abbrev(last_cwd))
    if convs:
        lines.append("| Conversations | %d (%s) |" % (len(convs), ", ".join(sorted({c["agent"] for c in convs}))))
    if gctx:
        lines.append("| Git | %s @ `%s`%s |" % (
            os.path.basename(gctx["root"]), gctx.get("branch") or "?",
            " (dirty)" if gctx.get("dirty") else "",
        ))
    lines.append(
        "| Output capture | %s |"
        % ("on (transcript below)" if raw else "off (commands only)")
    )
    lines.append("")

    lines.append("## Commands")
    lines.append("")
    if cmds:
        lines.append("| Time | Dir | Command | Exit | Duration |")
        lines.append("|---|---|---|---|---|")
        for c in cmds:
            cmd = redact(c.get("cmd", ""), patterns)
            ex = c.get("exit", "")
            mark = "" if str(ex) == "0" else " ⚠️"
            lines.append(
                "| %s | `%s` | `%s` | %s%s | %s |"
                % (
                    hhmmss(c.get("ts")),
                    cell(abbrev(c.get("cwd", ""))),
                    cell(cmd),
                    ex,
                    mark,
                    fmt_dur(c.get("dur_ms")),
                )
            )
    else:
        lines.append("_No commands recorded yet._")
    lines.append("")

    if convs:
        lines.append("## Conversation")
        lines.append("")
        lines.append("AI CLI conversations correlated to this terminal (same directory, overlapping time):")
        lines.append("")
        for d in convs:
            lines.append("### %s — %s" % (d["agent"], redact(d.get("title") or d["conv_id"], patterns)))
            lines.append("")
            lines.append("- id: `%s`  ·  turns: %s  ·  dir: `%s`" % (
                d["conv_id"], d.get("turns", "?"), abbrev(d.get("cwd") or "")))
            if d.get("render_file"):
                lines.append("- full transcript: `conversations/%s`" % d["render_file"])
            lines.append("")

    if gctx:
        lines.append("## Files changed & git")
        lines.append("")
        lines.append("- repo: `%s` · branch: `%s`%s" % (
            abbrev(gctx["root"]), gctx.get("branch") or "?",
            " · working tree dirty" if gctx.get("dirty") else ""))
        if gctx.get("commits"):
            lines.append("- commits this session:")
            for c in gctx["commits"]:
                lines.append("  - %s" % redact(c, patterns))
        if gctx.get("changed"):
            lines.append("")
            lines.append("| Added | Removed | File |")
            lines.append("|---|---|---|")
            for ch in gctx["changed"]:
                lines.append("| %s | %s | `%s` |" % (ch["added"], ch["removed"], cell(ch["path"])))
        diff = (gctx.get("diff") or "").strip()
        if diff:
            capped = diff[:200000]
            lines.append("")
            lines.append("<details><summary>Diff</summary>")
            lines.append("")
            lines.append("```diff")
            lines.append(redact(capped, patterns))
            if len(diff) > len(capped):
                lines.append("... (diff truncated)")
            lines.append("```")
            lines.append("")
            lines.append("</details>")
            # Also keep the raw patch alongside, for machine use.
            with open(_p("diff", sid + ".patch"), "w", encoding="utf-8") as fh:
                fh.write(redact(diff, patterns))
        lines.append("")

    env = meta.get("env") or {}
    if trail or env:
        lines.append("## Context trail")
        lines.append("")
        if trail:
            lines.append("Directories visited:")
            lines.append("")
            for d in trail:
                lines.append("- `%s`" % abbrev(d))
            lines.append("")
        if env:
            lines.append("Environment at start:")
            lines.append("")
            lines.append("| Var | Value |")
            lines.append("|---|---|")
            for k in sorted(env):
                lines.append("| %s | `%s` |" % (k, cell(redact(str(env[k]), patterns))))
            lines.append("")

    if raw:
        transcript = redact(clean_typescript(raw), patterns)
        lines.append("## Transcript (commands + output)")
        lines.append("")
        lines.append("```text")
        lines.append(transcript)
        lines.append("```")
        lines.append("")

    lines.append("---")
    lines.append("_Rendered by recall at %s. Secrets redacted as `%s`._" % (now_iso(), REDACTION))
    lines.append("")

    # Titled filename: remove a stale render if the title (and thus name) changed.
    out_path = _p("sessions", fname)
    prev = meta.get("_last_render_file")
    if prev and prev != fname:
        old = _p("sessions", prev)
        if os.path.isfile(old):
            try:
                os.remove(old)
            except OSError:
                pass
    meta["_last_render_file"] = fname
    write_json(_p("meta", sid + ".json"), meta)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return out_path


def all_session_ids():
    # Derive ids from the low-level streams only — sessions/*.md now have titled names, not ids.
    ids = set()
    for pat in ("meta/*.json", "cmd/*.jsonl", "raw/*.log"):
        for path in glob.glob(_p(*pat.split("/"))):
            base = os.path.basename(path)
            ids.add(base[:-6] if base.endswith(".jsonl") else base.rsplit(".", 1)[0])
    return ids


def session_render_path(sid):
    """Where a session's Markdown lives. Filenames are titled, so look it up from meta and fall
    back to rendering if we haven't computed one yet."""
    meta = read_json(_p("meta", sid + ".json")) or {}
    fname = meta.get("render_file")
    if fname and os.path.isfile(_p("sessions", fname)):
        return _p("sessions", fname)
    return render_session(sid)


def session_summary(sid):
    meta = read_json(_p("meta", sid + ".json")) or {}
    cmds = read_cmds(sid)
    first = ""
    for c in cmds:
        if c.get("cmd", "").strip():
            first = c["cmd"].strip().splitlines()[0]
            break
    return {
        "id": sid,
        "title": meta.get("title", ""),
        "render_file": meta.get("render_file", ""),
        "started": meta.get("started", ""),
        "ended": meta.get("ended"),
        "window": meta.get("window", ""),
        "host": meta.get("host", ""),
        "commands": len(cmds),
        "last_cwd": meta.get("last_cwd", cmds[-1]["cwd"] if cmds else ""),
        "first_cmd": first,
    }


def rebuild_index():
    rows = [session_summary(sid) for sid in all_session_ids()]
    rows.sort(key=lambda r: r["started"], reverse=True)
    lines = ["# Recall — session index", ""]
    lines.append("%d session(s) captured. Newest first." % len(rows))
    lines.append("")
    lines.append("| Title | Started | Status | Cmds | Last dir | Terminal id |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        status = "ended" if r["ended"] else "active"
        title = r["title"] or r["first_cmd"] or "(untitled)"
        link = "[%s](sessions/%s)" % (cell(title), r["render_file"]) if r["render_file"] else cell(title)
        lines.append(
            "| %s | %s | %s | %d | `%s` | `%s` |"
            % (
                link,
                r["started"] or "?",
                status,
                r["commands"],
                cell(abbrev(r["last_cwd"])),
                r["id"],
            )
        )
    lines.append("")
    with open(_p("index.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return rows


# --------------------------------------------------------------------------- commands


def cmd_begin(args):
    ensure_dirs()
    sid = os.environ.get("RECALL_SESSION_ID") or args.session
    if not sid:
        sys.exit("recall: no session id (RECALL_SESSION_ID unset)")
    mp = _p("meta", sid + ".json")
    meta = read_json(mp) or {}
    meta.setdefault("id", sid)
    meta.setdefault("started", now_iso())
    meta["host"] = socket.gethostname()
    meta["shell"] = os.environ.get("SHELL", "")
    tty = os.environ.get("RECALL_TTY", "")
    if not tty:
        try:
            tty = os.ttyname(0)
        except OSError:
            tty = ""
    meta["tty"] = tty
    meta["window"] = os.environ.get("RECALL_WINDOW", "")
    meta["recording"] = bool(os.environ.get("RECALL_RECORDING"))
    # Capture the starting git state and a small env allowlist so render can show what changed and
    # under what conditions the work happened.
    if "git_start" not in meta:
        gs = git_state(os.getcwd())
        if gs:
            meta["git_start"] = gs
    meta.setdefault("env", capture_env())
    write_json(mp, meta)
    print(sid)


def cmd_ingest(args):
    """Discover AI CLI conversations and render each to a titled transcript, so later session
    renders can correlate and inline them. Safe to run repeatedly (idempotent by conv key)."""
    ensure_dirs()
    patterns = load_patterns()
    convs = adapters.discover(cwds=all_known_cwds())
    n = 0
    for conv in convs:
        try:
            render_conversation(conv, patterns)
            n += 1
        except Exception:  # noqa: BLE001 — one bad transcript must not abort the rest
            continue
    if not getattr(args, "quiet", False):
        print("ingested %d conversation(s) -> %s" % (n, _p("conversations")))
    return n


def cmd_finalize(args):
    sid = args.session or os.environ.get("RECALL_SESSION_ID")
    if not sid:
        sys.exit("recall: finalize needs a session id")
    mp = _p("meta", sid + ".json")
    meta = read_json(mp) or {"id": sid}
    meta["ended"] = now_iso()
    write_json(mp, meta)
    cmd_ingest(argparse.Namespace(quiet=True))
    render_session(sid)
    rebuild_index()


def cmd_render(args):
    patterns = load_patterns()
    if args.all or not args.session:
        ids = all_session_ids()
    else:
        ids = [args.session]
    for sid in ids:
        render_session(sid, patterns)
    rebuild_index()
    print("rendered %d session(s) -> %s" % (len(ids), _p("sessions")))


def cmd_snapshot(args):
    cmd_ingest(argparse.Namespace(quiet=True))
    args.all = True
    args.session = None
    cmd_render(args)


def cmd_list(args):
    rows = rebuild_index()
    if not rows:
        print("no sessions captured yet")
        return
    for r in rows:
        status = "ended" if r["ended"] else "ACTIVE"
        label = r["title"] or r["first_cmd"] or "(untitled)"
        print(
            "%-20s %-7s %3d cmds  %-16s  %s"
            % (r["id"], status, r["commands"], abbrev(r["last_cwd"]), label[:60])
        )


def _resolve_sid(token):
    """Resolve a user-supplied token to a session id. Accepts an exact id, `last`/empty (this
    window else most recent), or a substring of the id / title / render filename."""
    rows = rebuild_index()
    if not rows:
        return None
    if token and token != "last":
        for r in rows:
            if r["id"] == token:
                return r["id"]
        t = token.lower()
        for r in rows:
            hay = " ".join((r["id"], r.get("title", ""), r.get("render_file", ""))).lower()
            if t in hay:
                return r["id"]
        return token  # let downstream report "nothing there"
    # prefer this window if we can identify it, else the most recent
    win = os.environ.get("RECALL_WINDOW")
    if win:
        for r in rows:
            if r["window"] == win and r["id"] != os.environ.get("RECALL_SESSION_ID"):
                return r["id"]
    return rows[0]["id"]


def cmd_show(args):
    sid = _resolve_sid(args.session)
    if not sid:
        print("no sessions to show")
        return
    path = session_render_path(sid)
    print(path)
    print()
    print(read_text(path))


def cmd_search(args):
    term = args.term
    rx = re.compile(re.escape(term), re.IGNORECASE)
    hits = 0
    for sid in sorted(all_session_ids()):
        path = session_render_path(sid)
        for i, line in enumerate(read_text(path).splitlines(), 1):
            if rx.search(line):
                print("%s:%d: %s" % (sid, i, line.strip()[:160]))
                hits += 1
    if not hits:
        print("no matches for %r" % term)


def cmd_resume(args):
    sid = _resolve_sid(args.session or ("window" if args.window else "last"))
    if not sid:
        print("no previous session to resume")
        return
    s = session_summary(sid)
    path = session_render_path(sid)
    cmds = read_cmds(sid)
    print("Resuming context from session %s" % sid)
    if s["title"]:
        print("  title   : %s" % s["title"])
    print("  started : %s" % s["started"])
    print("  window  : %s" % (s["window"] or "-"))
    print("  last dir: %s" % abbrev(s["last_cwd"]))
    if s["last_cwd"]:
        print("  -> cd %s" % s["last_cwd"])
    print("  last commands:")
    for c in cmds[-args.n :]:
        print("    %s  %s" % (hhmmss(c.get("ts")), c.get("cmd", "").splitlines()[0] if c.get("cmd") else ""))
    print("  full log: %s" % path)


def cmd_redact(args):
    patterns = load_patterns()
    text = read_text(args.file)
    sys.stdout.write(redact(text, patterns))


def cmd_setup(args):
    integ_zsh = os.path.join(_script_dir(), "recall.zsh")
    integ_bash = os.path.join(_script_dir(), "recall.bash")
    installer = os.path.join(_script_dir(), "install-scheduler.sh")
    print("recall setup")
    print("  1. Add to your ~/.zshrc:   source %s" % integ_zsh)
    print("     or to your ~/.bashrc:   source %s" % integ_bash)
    print("  2. Install the interval snapshotter: sh %s --interval %d" % (installer, args.interval))
    print("  3. Open a new terminal — capture starts automatically.")
    if not args.apply:
        print("\n(dry run — re-run with --apply to append the source line automatically)")
        return
    added = []
    for rc, integ in ((os.path.expanduser("~/.zshrc"), integ_zsh),):
        line = "source %s" % integ
        existing = read_text(rc)
        if "recall.zsh" not in existing:
            with open(rc, "a", encoding="utf-8") as fh:
                fh.write("\n# recall — terminal session history\n%s\n" % line)
            added.append(rc)
    print("appended to: %s" % (", ".join(added) if added else "(already present)"))
    print("now run: sh %s --interval %d" % (installer, args.interval))


# --------------------------------------------------------------------------- cli


def main(argv):
    ap = argparse.ArgumentParser(prog="recall", description="capture & recall terminal sessions")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("begin"); p.add_argument("session", nargs="?"); p.set_defaults(fn=cmd_begin)
    p = sub.add_parser("finalize"); p.add_argument("session", nargs="?"); p.set_defaults(fn=cmd_finalize)
    p = sub.add_parser("render"); p.add_argument("--session"); p.add_argument("--all", action="store_true"); p.set_defaults(fn=cmd_render)
    p = sub.add_parser("snapshot"); p.set_defaults(fn=cmd_snapshot)
    p = sub.add_parser("ingest"); p.add_argument("--quiet", action="store_true"); p.set_defaults(fn=cmd_ingest)
    p = sub.add_parser("list"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("show"); p.add_argument("session", nargs="?", default="last"); p.set_defaults(fn=cmd_show)
    p = sub.add_parser("search"); p.add_argument("term"); p.set_defaults(fn=cmd_search)
    p = sub.add_parser("resume"); p.add_argument("session", nargs="?"); p.add_argument("--window", action="store_true"); p.add_argument("-n", type=int, default=10); p.set_defaults(fn=cmd_resume)
    p = sub.add_parser("redact"); p.add_argument("file"); p.set_defaults(fn=cmd_redact)
    p = sub.add_parser("setup"); p.add_argument("--apply", action="store_true"); p.add_argument("--interval", type=int, default=300); p.set_defaults(fn=cmd_setup)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main(sys.argv[1:])
