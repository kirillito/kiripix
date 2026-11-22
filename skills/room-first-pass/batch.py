"""First passes over a list of rooms: one fresh Claude Code session per room, in sequence.

Run from the art Project's folder (where `kiripix.toml` is), after copying this skill to `.claude/skills/room-first-pass/`:

    python .claude/skills/room-first-pass/batch.py --match "room.ch01_dungeon_*"
    python .claude/skills/room-first-pass/batch.py room.ch01_dungeon_r01 room.ch01_dungeon_r02

Rooms run one after another, never side by side: their Runners share the GPU. Each room gets its own `claude -p` session with
the single-room skill (SKILL.md) in batch mode, so no room's context grows with the others', and each room's tokens come from
that session's own `usage` (`--output-format json`). A room with no Source is skipped with a line in the report, never guessed.

The report goes to `.kiripix/first-passes/<date>.md`: per room, where it stopped, its hand-over notes, its Decisions per Stage
in this pass and its tokens; then `kiripix queue --match <glob>` as the Owner's starting point.

Standard library only, so it runs with any Python 3.10 or later. It reads the Project only through Kiripix's Commands.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SKILL = Path(__file__).resolve().parent / "SKILL.md"

PROMPT = """Take {room} through its first pass, following the room-first-pass skill ({skill}).

You are in BATCH MODE: a driver runs one session per room and nobody reads this conversation. So:
- Never ask the Owner anything and never wait. Where the skill says to stop for the Owner, record every Decision you still can
  (Masks, `place`), write the hand-over note on the Stage that waits (`kiripix note`), and end the session.
- If you can't find the room's size and mood (no brief values set and no room design you can read), write a note on `brief`
  saying what is missing and end. Never guess a brief.
- Where you need a Command Kiripix lacks, say so in a note; don't script around it.
End with one short paragraph: where you stopped and why."""

USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


@dataclass
class RoomPass:
    room: str
    skipped: str | None = None
    stop: str = ""
    notes: list[str] = field(default_factory=list)
    decisions: dict[str, int] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=dict)
    cost_usd: float | None = None
    minutes: float = 0.0
    summary: str = ""
    error: str | None = None

    @property
    def tokens(self) -> int:
        return sum(self.usage.get(k, 0) for k in USAGE_KEYS)


def kiripix(cmd: list[str], *args: str) -> dict[str, Any]:
    """One Kiripix Command with --json; the envelope, whatever its exit code (2 and 3 still print one)."""
    proc = subprocess.run([*cmd, *args, "--json"], capture_output=True, text=True, encoding="utf-8")
    try:
        envelope: dict[str, Any] = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"`{' '.join([*cmd, *args])}` printed no JSON (exit {proc.returncode}): {proc.stderr.strip()}") from exc
    if envelope.get("data") is None:
        found = "; ".join(f"{f['code']}: {f['message']}" for f in envelope.get("findings", []))
        raise SystemExit(f"`{' '.join([*cmd, *args])}` failed: {found or 'no data'}")
    return envelope


def rooms_for(cmd: list[str], match: str | None, ids: list[str]) -> list[str]:
    if ids:
        return ids
    assert match is not None
    data = kiripix(cmd, "status", "--match", match)["data"]
    return sorted(a["asset"] for a in data["assets"] if a["kind"] == "room" and fnmatch.fnmatchcase(a["asset"], match))


def decisions_by_stage(cmd: list[str], room: str) -> dict[str, int]:
    data = kiripix(cmd, "stats", room)["data"]
    stages = data["assets"][0]["stages"] if data["assets"] else []
    return {s["stage"]: int(s["decisions"]) for s in stages}


def cannot_start(cmd: list[str], room: str) -> str | None:
    """Why no session should start on the room: no Source, or a live note on `brief` from an earlier pass saying what's
    missing (a new pass would only find the same gap). None when a session can start."""
    shown = kiripix(cmd, "show", room)["data"]
    if not shown.get("variants"):
        return "no Source: paint it (`kiripix to-paint`), then `import` it or drop it in the inbox"
    for stage in shown.get("stages", []):
        if stage.get("stage") == "brief" and stage.get("status") != "done":
            held = [n["text"] for n in stage.get("notes", []) if n.get("live")]
            if held:
                return "no brief: `brief`: " + "; ".join(held)
    return None


def where_it_stopped(cmd: list[str], room: str) -> tuple[str, list[str]]:
    nxt = kiripix(cmd, "next", room)["data"]
    if nxt.get("done"):
        stop = "done"
    else:
        stop = f"`{nxt.get('stage')}` {nxt.get('status')}"
        if nxt.get("owner_action"):
            stop += f": {nxt['owner_action']}"
    # `show` has every Stage's notes; `queue` only those on a stop, and a note on a `todo` brief is no stop.
    shown = kiripix(cmd, "show", room)["data"]
    notes = [f"`{s['stage']}`: {n['text']}" for s in shown.get("stages", []) for n in s.get("notes", []) if n.get("live")]
    return stop, notes


def run_session(args: argparse.Namespace, room: str) -> tuple[dict[str, Any] | None, str | None]:
    prompt = PROMPT.format(room=room, skill=SKILL.as_posix())
    claude = [*shlex.split(args.claude), "-p", prompt, "--output-format", "json"]
    if args.allowed_tools:
        claude += ["--allowedTools", *args.allowed_tools.split()]
    if args.model:
        claude += ["--model", args.model]
    try:
        proc = subprocess.run(claude, capture_output=True, text=True, encoding="utf-8",
                              timeout=args.timeout * 60 if args.timeout else None)
    except subprocess.TimeoutExpired:
        return None, f"the session ran past --timeout {args.timeout} min and was stopped"
    try:
        result: dict[str, Any] = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, f"claude exited {proc.returncode} with no JSON result: {proc.stderr.strip()[:500]}"
    if result.get("is_error"):
        return result, f"the session ended in an error: {str(result.get('result', ''))[:500]}"
    return result, None


def first_pass(args: argparse.Namespace, cmd: list[str], room: str) -> RoomPass:
    rp = RoomPass(room)
    skip = cannot_start(cmd, room)
    if skip:
        rp.skipped = skip
        return rp
    before = decisions_by_stage(cmd, room)
    started = time.monotonic()
    result, error = run_session(args, room)
    rp.minutes = (time.monotonic() - started) / 60
    rp.error = error
    if result:
        rp.usage = {k: int(v) for k, v in (result.get("usage") or {}).items() if k in USAGE_KEYS}
        rp.cost_usd = result.get("total_cost_usd")
        rp.summary = str(result.get("result") or "").strip()
    after = decisions_by_stage(cmd, room)
    rp.decisions = {s: n - before.get(s, 0) for s, n in after.items() if n - before.get(s, 0)}
    rp.stop, rp.notes = where_it_stopped(cmd, room)
    brief_notes = [n for n in rp.notes if n.startswith("`brief`")]
    if rp.stop.startswith("`brief`") and brief_notes and not rp.error:
        rp.skipped = "no brief: " + "; ".join(brief_notes)
    return rp


def report(passes: list[RoomPass], scope: str, started: dt.datetime) -> str:
    out = [f"# First passes, {started:%Y-%m-%d %H:%M}", "", f"Scope: `{scope}`. One `claude -p` session per room, in sequence.", ""]
    done = [p for p in passes if not p.skipped]
    out += ["| Room | Stopped at | Decisions this pass | Tokens | Minutes |", "|---|---|---|---|---|"]
    for p in done:
        decided = ", ".join(f"{s} {n}" for s, n in sorted(p.decisions.items())) or "none"
        out.append(f"| `{p.room}` | {p.stop} | {decided} | {p.tokens:,} | {p.minutes:.1f} |")
    if done:
        total = sum(p.tokens for p in done)
        cost = sum(p.cost_usd or 0 for p in done)
        out += ["", f"Total: {total:,} tokens over {len(done)} rooms (reported cost ${cost:.2f})."]
    for p in done:
        out += ["", f"## `{p.room}`", "", f"Stopped at {p.stop}."]
        if p.error:
            out += ["", f"**Error:** {p.error}"]
        if p.notes:
            out += ["", "Hand-over notes:", *[f"- {n}" for n in p.notes]]
        if p.usage:
            out += ["", "Tokens: " + ", ".join(f"{k} {v:,}" for k, v in p.usage.items())]
        if p.summary:
            out += ["", "The session's last words:", "", *[f"> {line}" if line else ">" for line in p.summary.splitlines()]]
    skipped = [p for p in passes if p.skipped]
    if skipped:
        out += ["", "## Skipped", "", *[f"- `{p.room}`: {p.skipped}" for p in skipped]]
    out += ["", "## For the Owner", ""]
    if scope.startswith("{"):  # room IDs, not a glob: `--match` takes one glob, so one line per room
        rooms = [p.room for p in passes]
        out += ["Start with `kiripix queue`, room by room; afterwards `kiripix stats` measures the queue sitting:", "",
                *[f"- `kiripix queue --match \"{r}\"`, then `kiripix stats {r}`" for r in rooms], ""]
    else:
        out += [f"Start with `kiripix queue --match \"{scope}\"`; afterwards `kiripix stats --match \"{scope}\"`",
                "measures the queue sitting.", ""]
    return "\n".join(out)


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rooms", nargs="*", help="Room IDs, such as room.ch01_dungeon_r01. Or use --match.")
    ap.add_argument("--match", help="A glob of room IDs, such as room.ch01_dungeon_*.")
    ap.add_argument("--kiripix", default="kiripix", help="How to run Kiripix (default: kiripix).")
    ap.add_argument("--claude", default="claude", help="How to run Claude Code (default: claude).")
    ap.add_argument("--allowed-tools", default="Bash(kiripix:*) Bash(kpx:*) Read Write Edit Glob Grep",
                    help="Tools each session may use without asking, space-separated (claude --allowedTools).")
    ap.add_argument("--model", help="claude --model for every session.")
    ap.add_argument("--timeout", type=float, default=60, help="Minutes before a room's session is stopped (0: never).")
    ap.add_argument("--report", type=Path, help="Where to write the report (default: .kiripix/first-passes/<date>.md).")
    ap.add_argument("--dry-run", action="store_true", help="List the rooms and the ones skipped; start no session.")
    args = ap.parse_args(argv)
    if bool(args.rooms) == bool(args.match):
        ap.error("give room IDs or --match, not both and not neither")

    cmd = shlex.split(args.kiripix)
    started = dt.datetime.now()
    rooms = rooms_for(cmd, args.match, args.rooms)
    if not rooms:
        print(f"No rooms match {args.match!r}.", file=sys.stderr)
        return 1
    scope = args.match or (rooms[0] if len(rooms) == 1 else "{" + ",".join(rooms) + "}")

    if args.dry_run:
        for room in rooms:
            skip = cannot_start(cmd, room)
            print(f"{room}: {'skip, ' + skip if skip else 'would run'}")
        return 0

    passes = []
    for i, room in enumerate(rooms, 1):
        print(f"[{i}/{len(rooms)}] {room} ...", file=sys.stderr, flush=True)
        rp = first_pass(args, cmd, room)
        print(f"    {('skipped: ' + rp.skipped) if rp.skipped else rp.stop} ({rp.tokens:,} tokens)", file=sys.stderr)
        passes.append(rp)
        # The report is rewritten after every room, so a stopped batch still leaves one.
        path = args.report or Path(".kiripix") / "first-passes" / f"{started:%Y-%m-%d}.md"
        write_atomic(path, report(passes, scope, started))
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
