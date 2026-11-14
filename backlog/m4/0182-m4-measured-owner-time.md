---
status: done
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

- [x] CLI seam: `track` refuses without the Owner (exit 3) and appends a span with it; `stats --json` on a Project with
      spans and journal entries gives the right minutes and counts per Stage, and `--since` drops the older ones.
- [x] Two branches that each append spans merge with no conflict, and `stats` counts both.
- [x] Contract samples for `track` and `stats`.
- [ ] The UI: ten minutes on a room's masks screen with a five-minute pause in the middle records about seven minutes
      (Owner, by hand, recorded here).
- [x] The CLI half is built or dropped in writing.

Budget: 150–250k tokens. The UI half is small (a hook on the Stage screens); if it grows past that, split it out for
`ui-engineer`.

## Result

Built (2026-11-13):

- `kiripix/core/timespans.py` (spans, `stats` maths, the CLI's count), `kiripix/commands/timing.py` (`track`, owner-only,
  never an MCP tool; `stats`, a Probe). A span's `source` is `ui` over the session token and `cli` at a terminal; `track`
  has no `source` option, so nothing can claim one. Findings: `time.invalid`, `time.stage_unknown`,
  `time.seconds_invalid`, `stats.since_invalid`, `time.merge_attribute_missing`.
- `kiripix init` writes `time.jsonl merge=union text eol=lf`. An existing Project gets it by hand: `track` warns with
  `time.merge_attribute_missing` (an `owner_action`) while its `.gitattributes` lacks the line.
- The UI hook, `web/src/activeTime.ts` (`useActiveTime`, called once in `App.tsx` for the open Asset and Stage): a visible,
  focused tab with an input in the last 3 minutes is active; a span is sent on blur, hide, idle, leaving the screen, tab
  close (keepalive) and every 60 s. The folder watch skips `time.jsonl`, or the UI would refresh itself every minute.
- **CLI half: built.** `invoke` (about 15 lines, imports lazily, only for `interactive` CLI calls) counts, for a writing or
  owner-only Command naming an Asset and a Stage (`extend` counts as the stage `extend`), the time from the end of the
  Owner's previous such Command on that Asset to the start of this one, when under 3 minutes. The previous end is kept in
  `.kiripix/cli-time.json`. `KIRIPIX_TEST_OWNER` doesn't count (it isn't a terminal), so the test drives `invoke` with an
  interactive Context.
- `stats` counts a Decision entry without `replaces`, and undo and redo entries; `--since` filters by the ULID's time
  (a date is local midnight).

Still the Owner's: the ten-minute masks screen check (the idle rule is the literal one, so the five-minute pause counts
its first three minutes: expect about eight, not seven; say if that should be stricter).

## Closing notes (2026-11-13)

- Closed 2026-11-13; the ten-minute UI check stays the Owner's, by hand, to be recorded here.
