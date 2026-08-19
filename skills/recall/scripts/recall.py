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
import json
import os
import re
import socket
import sys
import time
from datetime import datetime

REDACTION = "«redacted»"


# --------------------------------------------------------------------------- paths


def home():
    return os.environ.get("RECALL_HOME", os.path.expanduser("~/.recall"))


def _p(*parts):
    return os.path.join(home(), *parts)


def ensure_dirs():
    for d in ("raw", "cmd", "meta", "sessions"):
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


# --------------------------------------------------------------------------- render


def render_session(sid, patterns=None):
    if patterns is None:
        patterns = load_patterns()
    meta = read_json(_p("meta", sid + ".json")) or {"id": sid}
    cmds = read_cmds(sid)
    raw = read_text(_p("raw", sid + ".log"), newline="")

    last_cwd = cmds[-1]["cwd"] if cmds else meta.get("last_cwd", "")
    meta["last_cwd"] = last_cwd
    meta["commands"] = len(cmds)
    write_json(_p("meta", sid + ".json"), meta)

    lines = []
    lines.append("# Terminal session `%s`" % sid)
    lines.append("")
    status = "ended %s" % meta["ended"] if meta.get("ended") else "**active**"
    lines.append("| | |")
    lines.append("|---|---|")
    lines.append("| Started | %s |" % meta.get("started", "?"))
    lines.append("| Status | %s |" % status)
    lines.append("| Host | %s |" % meta.get("host", "?"))
    lines.append("| Shell | %s |" % meta.get("shell", "?"))
    lines.append("| TTY | %s |" % meta.get("tty", "?"))
    if meta.get("window"):
        lines.append("| Window | `%s` |" % meta["window"])
    lines.append("| Commands | %d |" % len(cmds))
    lines.append("| Last dir | `%s` |" % abbrev(last_cwd))
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

    ensure_dirs()
    out_path = _p("sessions", sid + ".md")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return out_path


def all_session_ids():
    ids = set()
    for pat in ("meta/*.json", "cmd/*.jsonl", "raw/*.log", "sessions/*.md"):
        for path in glob.glob(_p(*pat.split("/"))):
            base = os.path.basename(path)
            ids.add(base.rsplit(".", 1)[0].split(".")[0] if base.endswith(".jsonl") else base.rsplit(".", 1)[0])
    return ids


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
    lines.append("| Session | Started | Status | Window | Cmds | Last dir | First command |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        status = "ended" if r["ended"] else "active"
        lines.append(
            "| `%s` | %s | %s | `%s` | %d | `%s` | `%s` |"
            % (
                r["id"],
                r["started"] or "?",
                status,
                cell(r["window"]),
                r["commands"],
                cell(abbrev(r["last_cwd"])),
                cell(r["first_cmd"]),
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
    write_json(mp, meta)
    print(sid)


def cmd_finalize(args):
    sid = args.session or os.environ.get("RECALL_SESSION_ID")
    if not sid:
        sys.exit("recall: finalize needs a session id")
    mp = _p("meta", sid + ".json")
    meta = read_json(mp) or {"id": sid}
    meta["ended"] = now_iso()
    write_json(mp, meta)
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
        print(
            "%-28s %-7s %3d cmds  %-16s  %s"
            % (r["id"], status, r["commands"], abbrev(r["last_cwd"]), r["first_cmd"][:50])
        )


def _resolve_sid(token):
    if token and token != "last":
        return token
    rows = rebuild_index()
    if not rows:
        return None
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
    render_session(sid)
    path = _p("sessions", sid + ".md")
    print(path)
    print()
    print(read_text(path))


def cmd_search(args):
    term = args.term
    rx = re.compile(re.escape(term), re.IGNORECASE)
    hits = 0
    for sid in sorted(all_session_ids()):
        render_session(sid)
        for i, line in enumerate(read_text(_p("sessions", sid + ".md")).splitlines(), 1):
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
    render_session(sid)
    cmds = read_cmds(sid)
    print("Resuming context from session %s" % sid)
    print("  started : %s" % s["started"])
    print("  window  : %s" % (s["window"] or "-"))
    print("  last dir: %s" % abbrev(s["last_cwd"]))
    if s["last_cwd"]:
        print("  -> cd %s" % s["last_cwd"])
    print("  last commands:")
    for c in cmds[-args.n :]:
        print("    %s  %s" % (hhmmss(c.get("ts")), c.get("cmd", "").splitlines()[0] if c.get("cmd") else ""))
    print("  full log: %s" % _p("sessions", sid + ".md"))


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
