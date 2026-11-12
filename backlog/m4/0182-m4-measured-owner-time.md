---
status: todo
milestone: M4
agent: core-engineer
type: ticket
---

# M4: measure the Owner's time per Asset and Stage, and `kiripix stats`

Spec §5 (the Decision journal), §10.3 (owner-only Commands). Asked for by the game, 2026-11-12.

## The gap

The game's CP1 checkpoint, after its M09 (`urban-mystery-club/docs/ROADMAP.md`, "Checkpoints"; `MILESTONE_PLANS.md`
M09-07), needs the founder's measured hours and the art-correction time per room. Our gates record the Owner's time by
hand ([0142](0142-m4-gate.md) asks for it split into extending and the rest), which is a guess made after the fact.

The Decision journals already hold every Decision, undo and redo, each with a ULID that carries its time. Only the Owner's
active time is missing.

## What to build

- **`assets/<kind>/<id>/time.jsonl`**: committed, append-only, one span per line, LF, `merge=union` (the Owner's choice,
  2026-11-12: it survives clones and branches, like `history.jsonl`). A line is
  `{schema_version, id: <ULID>, stage, seconds, source: "ui"|"cli"}`; the ULID is the span's end. `stage` is a Stage of the
  Asset's Kind, or `extend` for the tool that runs before `source` (only Kiripix's part of it: making the pieces happens
  outside Kiripix and isn't measured). `kiripix init` adds it to the
  `.gitattributes` it writes, and the ticket says how an existing Project gets the line (a finding with a `fix`, or the
  Owner adds it by hand).
- **Active time** is time with the Stage's screen focused and an input event (pointer, key, wheel) in the last 3 minutes.
  The idle threshold is a constant; a `kiripix.toml` setting only if the Owner asks for one later.
- **`kiripix track <id> <stage> --seconds N`**: owner-only (§10.3: interactive terminal, or the UI's session token; never
  an MCP tool), so an agent can't log time. It appends one span; refuses `N` over an hour or under 1.
- **The UI** keeps a span per (Asset, Stage) screen and sends it with `track` on blur, on idle, on leaving the screen, and
  every 60 s while active, so a crash loses at most a minute. Nothing is sent while the tab is hidden.
- **The CLI, if cheap:** an owner-only or writing Command that names an Asset and a Stage, run from an interactive terminal
  (not through `KIRIPIX_TEST_OWNER`), counts the time since the Owner's previous such Command on the same Asset, when
  that is under the idle threshold (the previous one's time kept in `.kiripix/`). If this costs more than a few lines in
  `invoke`, or any start-up time against [0163](0163-m4-start-faster.md), drop it and say so here.
- **`kiripix stats <id>|--all [--since <date>] [--json]`**, read-only: per Asset and Stage, active minutes (UI and CLI
  apart, and their sum), Decisions, undos and redos from the journal (an `accept`'s re-recorded entries are not new
  Decisions), and totals. `--since` filters by ULID time. The journal doesn't say who decided, so Decisions include an
  agent's; say so in the Command's `description`.
- **No telemetry:** nothing leaves the machine; the only writes are `time.jsonl` and the `.kiripix/` file.

## Acceptance criteria

- [ ] CLI seam: `track` refuses without the Owner (exit 3) and appends a span with it; `stats --json` on a Project with
      spans and journal entries gives the right minutes and counts per Stage, and `--since` drops the older ones.
- [ ] Two branches that each append spans merge with no conflict, and `stats` counts both.
- [ ] Contract samples for `track` and `stats`.
- [ ] The UI: ten minutes on a room's masks screen with a five-minute pause in the middle records about seven minutes
      (Owner, by hand, recorded here).
- [ ] The CLI half is built or dropped in writing.

Budget: 150–250k tokens. The UI half is small (a hook on the Stage screens); if it grows past that, split it out for
`ui-engineer`.
