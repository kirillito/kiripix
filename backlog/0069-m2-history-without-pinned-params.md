---
status: done
milestone: M2
agent: core-engineer
type: ticket
---

# M2: `history.jsonl` doesn't repeat what `pinned/` already holds

Spec §5 (History), ADR 0002. **Changes the spec's History paragraph: the Owner agreed on 2026-11-05.**

## Why

`room.harbor_front`'s `history.jsonl` reached 138 KB in 279 lines in a day of work. 72% of it is Runner calls repeating
their full `params`: LaMa's hole as runs (79 KB, 42 lines, up to 5 KB each) and SAM 2's click points, where each new
negative click re-lists every point of its object (20 KB). Every such call has a `key`, and `pinned/<key>.json` already
records the same `params` with the `decisions`, `image_hash`, weights and licence. The file is committed (`merge=union`),
so it grows the repository too, and it's what the Owner hands to Claude to diagnose a run.

## What to build

- In `AssetGraph._call`'s `history(...)` (`kiripix/core/graph.py`): a call whose result was pinned writes `key` and no
  `params`. A call with no pinned result (`failed`, `cancelled`) keeps `params`, since nothing else records them.
- Spec §5, History: "plus the prompt, seed, parameters" becomes "plus the prompt, seed, and either the parameters or, when
  the result was pinned, its `key` (the parameters are in `pinned/<key>.json`)".
- Stage lines (no Runner) are unchanged: their `params` are a Stage's few parameters.
- No migration: lines already written stay as they are (append-only). A reader of `history.jsonl` must accept both.

## Acceptance criteria

- [x] A pinned Runner call's history line has `key` and no `params`; `pinned/<key>.json` has the `params` it would have had.
- [x] A failed and a cancelled Runner call still write `params`.
- [x] Nothing in Kiripix reads `params` from `history.jsonl` (checked by grep; say so in the Notes).

## Notes

Measured on `room.harbor_front`, 2026-11-05: the change would have made that file about 40 KB instead of 138 KB.
For diagnosing, ask Claude to filter by time and Stage rather than read the whole file.

Grep, 2026-11-05: `history.jsonl` is opened only by `kiripix/core/graph.py` (two `append_jsonl` writes), `core/assets.py` (creates it empty) and
`core/project.py` (the `.gitattributes` line). Nothing in `kiripix/` or `web/src/` reads it back, so nothing reads `params` from it; the
web e2e specs only read the file as text (`layers.spec.ts`, `masks.spec.ts`), not its `params`. Tests: `tests/cli/test_history_lines.py`.
