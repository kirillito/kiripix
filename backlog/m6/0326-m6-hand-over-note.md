---
status: done
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0327-m6-match-scope.md]
---

# M6: a hand-over note on a Stage

Spec §5, §10 and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md), written to the Owner's Q2 there.

## The gap

When a first pass stops for the Owner, the session knows why and what's left: "the bench's `solid` may be 16 px long", "two
lockers aren't lifted because they hug the wall". Today that is only in the session's last message. Across a district's
rooms ([0331](0331-m6-first-passes-over-a-list-of-rooms.md)), the Owner reviews long after the session ends.

## What to build

- `kiripix note <id> <stage> "<text>"` appends a note to the Asset's `notes.jsonl` (`schema_version` 1, a ULID, the Stage,
  the text, the Stage's input hash when written; append-only, one object per line, LF). `--json` returns the note.
- A note is **not a Decision**: it changes no output and no input hash, and `undo` doesn't reach it.
- **A note is live** while its Stage has no newer Decision and no `accept` since it was written. That is derived, never
  stored (ADR 0005). `show` lists a Stage's notes with `live` true or false. `queue`
  ([0325](0325-m6-review-queue-command.md)) shows the live ones beside the Stage's items.
- Anyone may write a note: an agent, the Owner, the UI. A note over 2,000 characters is refused (`note.too_long`).
- `describe` names the Command. The room first-pass skill uses it at every stop (0331 adds that).

## Acceptance criteria

- [x] CLI seam: a note is live after `note`, still live after `run`, and not live after a Decision on that Stage or an
      `accept` of it; `show` lists both kinds.
- [x] CLI seam: the file is append-only, and a note leaves every Stage's status and input hash unchanged.
- [x] `note` has a sample in `tests/cli/test_contract.py`.
- [x] The glossary says what a hand-over note is, and that it isn't a Decision.

## Result

`kiripix note <id> <stage> "<text>"` (`kiripix/commands/decisions.py`, core in `kiripix/core/notes.py`) appends a note to the Asset's
`notes.jsonl` (`schema_version` 1, ULID, Stage, text, the Stage's input hash) and returns it with `live`. Liveness is derived on
read: a note is live while its Stage's journal has no entry after it (a Decision, undo, redo or accept). `show` lists each Stage's
`notes` with `live`. For `queue` (0325): `notes.live_notes(asset)` gives each Stage's live notes in one pass, reading only the
journals of Stages that have notes. Refusals: `note.too_long` (over 2,000 characters), `note.empty`, `note.invalid` (a bad line or
unknown key in the file). A new Project's `.gitattributes` gets `notes.jsonl merge=union text eol=lf`; an existing Project's
`.gitattributes` is not rewritten, so the Owner should add that line. No `version` or `schema_version` bump; glossary and spec §3/§5 say what a
note is. Tests: `tests/cli/test_note.py`, plus samples in the contract and REST tests.


**Review fixes (2026-11-20):** Only a Decision or an `accept` ends a note, as the ticket says; an `undo` or a `redo` no longer does. A note's ULID now sorts after the Stage's latest journal entry too, so a note written in the same millisecond as a Decision is live. The other way round (a Decision in the same millisecond as a note) can still sort before it: the journal doesn't read `notes.jsonl`.
